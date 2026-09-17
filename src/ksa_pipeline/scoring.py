"""Phase 5 — lead scoring, tiers, Top-50 and sensitivity, driven by config/scoring.yaml.

Inputs (all local): data/interim/merchants.csv (stage 4), bnpl.csv (step 4.2) with the Tabby QA file, enrich.csv (step 4.3)
and config/icp.yaml. Every merchant keeps a row: excluded ones carry score_exclusion and no points.
"""
from __future__ import annotations

import copy
from bisect import bisect_right
from collections import Counter
from datetime import date
from functools import lru_cache

import yaml

from . import paths
from .fingerprint import QA_TABBY, final_tabby, read_csv, write_csv
from .schema import scored_columns

SCORED_COLUMNS = [c["name"] for c in scored_columns()]
DIRECT = ("mobile_or_whatsapp_and_name", "mobile_or_whatsapp", "instagram")


@lru_cache
def config() -> dict:
    return yaml.safe_load((paths.CONFIG / "scoring.yaml").read_text(encoding="utf-8"))


@lru_cache
def icp() -> dict:
    return yaml.safe_load((paths.CONFIG / "icp.yaml").read_text(encoding="utf-8"))


def _num(value, cast=float, default=0):
    try:
        return cast(float(value))
    except (TypeError, ValueError):
        return default


def ticket_points(segment: str, cfg: dict) -> int:
    c = cfg["components"]["ticket_fit"]
    low = icp()["segments"][segment]["expected_ticket_sar"][0]
    if low >= c["ltf_min_sar"]:
        return c["points"]["ltf"]
    return c["points"]["pay_in_4"] if low >= c["pay_in_4_min_sar"] else c["points"]["low"]


def bnpl_final(web: dict | None, qa: dict | None) -> str:
    status = (web or {}).get("bnpl_status") or ""
    if status == "tabby":
        return "tabby" if qa is None or final_tabby(qa) else "not_detected"
    return status if status in ("not_detected", "competitor_only", "generic_installment") else "unchecked"


def channel(m: dict, web: dict | None, name_verified: bool) -> str:
    w = web or {}
    maps_whatsapp = m.get("contactable") == "True" and m.get("phone_type") != "mobile" and not m.get("instagram_handle")
    mobile = m.get("phone_type") == "mobile" or maps_whatsapp or w.get("page_mobile") == "True" or w.get("page_whatsapp") == "True"
    if mobile:
        return "mobile_or_whatsapp_and_name" if name_verified else "mobile_or_whatsapp"
    if m.get("instagram_handle") or w.get("page_instagram") == "True":
        return "instagram"
    if m.get("phone_type") in ("landline", "unified", "tollfree") or w.get("page_phone") == "True":
        return "other_phone"
    return "none"


def quartile_cuts(values: list[int]) -> list[float]:
    s = sorted(values)
    if not s:
        return [0, 0, 0]
    return [s[min(int(len(s) * q), len(s) - 1)] for q in (0.25, 0.5, 0.75)]


def max_points(cfg: dict) -> float:
    comp = cfg["components"]
    t = comp["traction"]
    return (max(comp["ticket_fit"]["points"].values()) + max(comp["bnpl"]["points"].values())
            + max(t["reviews_quartile_points"]) + max(t["rating"]["high"], t["rating"]["mid"], t["rating"]["low"])
            + max(t["locations"]["multi"], t["locations"]["single"]) + max(comp["reachability"]["points"].values()))


def tier_cuts(cfg: dict) -> dict:
    top = max_points(cfg)
    return {k: round(v * top, 2) for k, v in cfg["tiers_share_of_max"].items()}


def build(cfg: dict | None = None) -> list[dict]:
    """Score every merchant with the given config (defaults to config/scoring.yaml)."""
    cfg = cfg or config()
    comp = cfg["components"]
    segments = icp()["segments"]
    web = {r["merchant_id"]: r for r in read_csv(paths.INTERIM / "bnpl.csv")}
    qa_path, enrich_path = paths.SAMPLES / QA_TABBY, paths.INTERIM / "enrich.csv"
    qa = {r["merchant_id"]: r for r in read_csv(qa_path)} if qa_path.exists() else {}
    enrich = {r["merchant_id"]: r for r in read_csv(enrich_path)} if enrich_path.exists() else {}
    cut = tier_cuts(cfg)
    rows = []
    for m in read_csv(paths.INTERIM / "merchants.csv"):
        mid, seg = m["merchant_id"], m["segment"]
        w, status = web.get(mid), bnpl_final(web.get(mid), qa.get(mid))
        exclusion = m["exclusion_reason"]
        if not exclusion and segments.get(seg, {}).get("status") == "rejected":
            exclusion = f"segment rejected: {segments[seg].get('rejection_reason', '')}"
        if not exclusion and status == "tabby":
            exclusion = "already Tabby merchant"
        named = (enrich.get(mid) or {}).get("owner_name_in_source") == "True"
        rows.append({"merchant_id": mid, "segment": seg, "cities": m["cities"], "name": m["name"], "score_exclusion": exclusion,
                     "bnpl_status_final": status, "reviews_count": _num(m["reviews_count"], int), "rating": m["rating"],
                     "n_locations": _num(m["n_locations"], int), "channel": channel(m, w, named), "owner_name_verified": named,
                     "hook_from_page": (enrich.get(mid) or {}).get("input_kind") == "page_text", "_web": w})
    cuts = {seg: quartile_cuts([r["reviews_count"] for r in rows if r["segment"] == seg and not r["score_exclusion"]])
            for seg in {r["segment"] for r in rows}}
    for r in rows:
        if r["score_exclusion"]:
            continue
        r["ticket_points"] = ticket_points(r["segment"], cfg)
        r["bnpl_points"] = comp["bnpl"]["points"][r["bnpl_status_final"]]
        r["reviews_quartile"] = 1 + bisect_right(cuts[r["segment"]], r["reviews_count"]) if r["reviews_count"] else 1
        t = comp["traction"]
        rating = _num(r["rating"], float, 0.0)
        rating_pts = t["rating"]["high"] if rating >= t["rating"]["high_min"] else t["rating"]["mid"] if rating >= t["rating"]["mid_min"] else t["rating"]["low"]
        loc = t["locations"]
        loc_pts = loc["multi"] if loc["multi_min"] <= r["n_locations"] <= loc["multi_max"] else loc["single"]
        r["traction_points"] = t["reviews_quartile_points"][r["reviews_quartile"] - 1] + rating_pts + loc_pts
        r["reachability_points"] = comp["reachability"]["points"][r["channel"]]
        r["score"] = round(r["ticket_points"] + r["bnpl_points"] + r["traction_points"] + r["reachability_points"], 2)
        r["tier"] = "A" if r["score"] >= cut["A"] else "B" if r["score"] >= cut["B"] else "C"
        r["direct_channel"] = r["channel"] in cfg["top_list"]["direct_channels"]
        flags = []
        if r["segment"].startswith("A_"):
            flags.append("medical: Risk review")
        if r["segment"].startswith("B_") and "jeddah" in r["cities"]:
            flags.append("B Jeddah: source relevance 0.40")
        if r["bnpl_status_final"] == "unchecked":
            flags.append("BNPL unchecked")
        r["flags"] = "; ".join(flags)
    top = top_list(rows, cfg)
    for i, r in enumerate(top, 1):
        r["top_rank"] = i
    if len(top) == cfg["top_list"]["size"]:               # merchants tied with the last member are a reserve, not a rank
        cutoff = top[-1]["score"]
        for r in rows:
            if (not r["score_exclusion"] and not r.get("top_rank") and r["tier"] == cfg["top_list"]["require_tier"]
                    and r["direct_channel"] and r["score"] == cutoff):
                r["flags"] = "; ".join(filter(None, [r["flags"], "reserve: tied at the Top-list cutoff score"]))
    return rows


def top_list(rows: list[dict], cfg: dict) -> list[dict]:
    t = cfg["top_list"]
    eligible = [r for r in rows if not r["score_exclusion"] and r["tier"] == t["require_tier"] and r["direct_channel"]]
    return sorted(eligible, key=lambda r: (-r["score"], -r["reviews_count"], r["merchant_id"]))[: t["size"]]


def scaled(cfg: dict, component: str, factor: float) -> dict:
    """Copy of the config with one component's points multiplied by factor (tiers unchanged)."""
    c = copy.deepcopy(cfg)
    comp = c["components"][component]
    if component == "traction":
        comp["reviews_quartile_points"] = [p * factor for p in comp["reviews_quartile_points"]]
        for key in ("high", "mid", "low"):
            comp["rating"][key] *= factor
        for key in ("multi", "single"):
            comp["locations"][key] *= factor
    else:
        comp["points"] = {k: v * factor for k, v in comp["points"].items()}
    return c


def sensitivity(base_top: list[dict], cfg: dict) -> list[dict]:
    base = {r["merchant_id"] for r in base_top}
    variants = [(f"{name} x{f}", scaled(cfg, name, f)) for name in cfg["components"] for f in cfg["sensitivity"]["weight_factors"]]
    for pts in cfg["sensitivity"]["bnpl_unchecked_points"]:
        c = copy.deepcopy(cfg)
        c["components"]["bnpl"]["points"]["unchecked"] = pts
        variants.append((f"bnpl unchecked = {pts}", c))
    out = []
    for label, c in variants:
        top = {r["merchant_id"] for r in top_list(build(c), c)}
        out.append({"variant": label, "top_size": len(top), "overlap": len(base & top) / len(base) if base else 0.0})
    return out


def _table(header: list[str], rows: list[list]) -> list[str]:
    return ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)] + ["| " + " | ".join(map(str, r)) + " |" for r in rows]


def run() -> dict:
    cfg = config()
    rows = build(cfg)
    write_csv(paths.INTERIM / "scored.csv", [{k: r.get(k, "") for k in SCORED_COLUMNS} for r in rows], SCORED_COLUMNS)
    top = [r for r in rows if r.get("top_rank")]
    sens = sensitivity(sorted(top, key=lambda r: r["top_rank"]), cfg)
    stable = all(v["overlap"] >= cfg["sensitivity"]["stable_if_top_overlap_at_least"] for v in sens)
    scored = [r for r in rows if not r["score_exclusion"]]
    segs = sorted({r["segment"] for r in scored})

    lines = ["# Lead scoring (phase 5)", "",
             f"Run {date.today().isoformat()}, `config/scoring.yaml` v{cfg['version']} (fixed before the first calculation). "
             f"Tiers: A >= {tier_cuts(cfg)['A']}, B >= {tier_cuts(cfg)['B']} of {max_points(cfg)}. Counts only; the lead list is in data/interim/scored.csv.", "",
             "## Scored and excluded", ""]
    lines += _table(["segment", "merchants", "scored", "excluded"],
                    [[s, sum(r["segment"] == s for r in rows), sum(r["segment"] == s for r in scored),
                      sum(r["segment"] == s and bool(r["score_exclusion"]) for r in rows)] for s in sorted({r["segment"] for r in rows})])
    reasons = Counter((r["segment"], r["score_exclusion"].split(":")[0]) for r in rows if r["score_exclusion"])
    lines += ["", "Exclusion reasons (grouped):", ""] + _table(["segment", "reason", "merchants"], [[*k, n] for k, n in sorted(reasons.items())])
    lines += ["", "## Tiers", ""]
    lines += _table(["segment", "A", "B", "C", "A with a direct channel", "median score"],
                    [[s, *[sum(r["segment"] == s and r["tier"] == t for r in scored) for t in "ABC"],
                      sum(r["segment"] == s and r["tier"] == "A" and r["direct_channel"] for r in scored),
                      sorted(r["score"] for r in scored if r["segment"] == s)[len([r for r in scored if r["segment"] == s]) // 2]]
                     for s in segs])
    lines += ["", "## Components (scored merchants)", ""]
    for field in ("bnpl_status_final", "channel", "reviews_quartile"):
        lines += _table(["segment", field, "merchants"], [[*k, n] for k, n in sorted(Counter((r["segment"], r[field]) for r in scored).items())]) + [""]
    lines += [f"## Top-{cfg['top_list']['size']} (A-tier with a direct channel)", "",
              f"Members: {len(top)}" + ("" if len(top) == cfg["top_list"]["size"] else " (fewer qualified; the list is not filled from B-tier)"), ""]
    if top:
        cutoff = min(r["score"] for r in top)
        tied = [r for r in scored if r["tier"] == "A" and r["direct_channel"] and r["score"] == cutoff]
        unchecked = [r["score"] for r in scored if r["bnpl_status_final"] == "unchecked"]
        lines += [f"Score range {max(r['score'] for r in top)} to {cutoff}. {sum(r['score'] > cutoff for r in top)} leads score above the "
                  f"cutoff; the other {sum(r['score'] == cutoff for r in top)} come from {len(tied)} merchants tied at {cutoff}, ordered by review "
                  f"count (order fixed in scoring.yaml). The remaining {sum('reserve:' in r['flags'] for r in scored)} are flagged as reserve. "
                  f"Best score with BNPL unchecked: {max(unchecked) if unchecked else '-'}.", ""]
    for field in ("segment", "cities", "bnpl_status_final", "channel", "owner_name_verified", "hook_from_page", "reviews_quartile"):
        lines += _table([field, "leads"], [[k, n] for k, n in sorted(Counter(str(r[field]) for r in top).items())]) + [""]
    lines += _table(["flag", "leads"], [[k, n] for k, n in sorted(Counter(f for r in top for f in r["flags"].split("; ") if f).items())]) + [""]
    lines += ["## Sensitivity", "",
              f"Each component's points x0.8 and x1.2 in turn (tier cuts follow the new maximum), and unchecked BNPL at 15 / 21. Stable if every variant "
              f"keeps >= {cfg['sensitivity']['stable_if_top_overlap_at_least']:.0%} of the Top-{cfg['top_list']['size']} (fixed before the run).", ""]
    lines += _table(["variant", "top size", "overlap with base"], [[v["variant"], v["top_size"], f"{v['overlap']:.2f}"] for v in sens])
    lines += ["", f"**Top list {'stable' if stable else 'NOT stable'}** (minimum overlap {min(v['overlap'] for v in sens):.2f})." if sens else ""]
    text = "\n".join(lines) + "\n"
    (paths.SAMPLES / "scoring_summary.md").write_text(text, encoding="utf-8")
    return {"rows": rows, "top": top, "sensitivity": sens, "stable": stable, "summary": text}
