"""Source validation: fill rates on the full run + ICP relevance on a hand-labelled sample.

Thresholds come from data/sources.yaml (validation_protocol), fixed before data.
The verdict is a recommendation; changing status in sources.yaml stays a manual,
dated decision.
"""
from __future__ import annotations

import csv
import random
from pathlib import Path

import yaml

from .normalize import mask_phone
from .paths import CONFIG, INTERIM, SAMPLES, SOURCES_YAML


def protocol() -> dict:
    return yaml.safe_load(SOURCES_YAML.read_text(encoding="utf-8"))["validation_protocol"]


def chain_threshold() -> int:
    return yaml.safe_load((CONFIG / "icp.yaml").read_text(encoding="utf-8"))["disqualifiers"]["chain_location_threshold"]


def load_interim(source_id: str, segment: str) -> list[dict]:
    rows = []
    for path in sorted((INTERIM / source_id).glob("*.csv")):
        with path.open(encoding="utf-8") as f:
            rows += [r for r in csv.DictReader(f) if r["segment"] == segment]
    seen, unique = set(), []
    for r in rows:  # same record across runs (sample run + full run) counted once
        if r["record_id"] not in seen:
            seen.add(r["record_id"])
            unique.append(r)
    return unique


def sample_path(source_id: str, segment: str) -> Path:
    return SAMPLES / f"{source_id}__{segment}__sample.csv"


def make_sample(source_id: str, segment: str) -> Path:
    p = protocol()
    rows = load_interim(source_id, segment)
    picked = random.Random(p["random_seed"]).sample(rows, min(p["sample_size"], len(rows)))
    fields = ["record_id", "name", "category_raw", "city", "phone_masked", "phone_type",
              "website_platform", "website_domain", "store_key", "instagram_handle",
              "name_location_count", "evidence_url", "icp_label", "label_note"]
    out = sample_path(source_id, segment)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        w.writeheader()
        for r in picked:
            w.writerow({**r, "phone_masked": mask_phone(r["phone_e164"]), "icp_label": "", "label_note": ""})
    return out


def _rate(rows: list[dict], predicate) -> float:
    return round(sum(1 for r in rows if predicate(r)) / len(rows), 3) if rows else 0.0


def metrics(source_id: str, segment: str) -> dict:
    rows = load_interim(source_id, segment)
    chain_t = chain_threshold()
    m = {
        "n_records": len(rows),
        "fill_phone_any": _rate(rows, lambda r: r["phone_e164"]),
        "fill_phone_mobile": _rate(rows, lambda r: r["phone_type"] == "mobile"),
        "fill_own_site": _rate(rows, lambda r: r["website_platform"] == "own_site"),
        "fill_instagram": _rate(rows, lambda r: r["instagram_handle"]),
        "contactable_rate": _rate(rows, lambda r: r["phone_type"] == "mobile" or r["instagram_handle"] or r["has_whatsapp_link"] == "True"),
        "closed_rate": _rate(rows, lambda r: r["is_closed"] == "True"),
        "chain_rate": _rate(rows, lambda r: r["name_location_count"] and int(r["name_location_count"]) > chain_t),
    }
    labels = []
    sp = sample_path(source_id, segment)
    if sp.exists():
        with sp.open(encoding="utf-8") as f:
            labels = [r["icp_label"].strip() for r in csv.DictReader(f)]
    labeled = [l for l in labels if l]
    m.update(
        sample_size=len(labels), labeled=len(labeled),
        fit=labeled.count("fit"), not_fit=labeled.count("not_fit"), unclear=labeled.count("unclear"),
        icp_relevance=round(labeled.count("fit") / len(labeled), 3) if labeled else None,
    )
    return m


def verdict(m: dict) -> str:
    t = protocol()["thresholds"]
    if m["n_records"] == 0:
        return "no_data"
    if m["labeled"] < m["sample_size"] or m["icp_relevance"] is None:
        return "incomplete: label every sample row (fit | not_fit | unclear)"
    failed = []
    if m["icp_relevance"] < t["icp_relevance_min"]:
        failed.append(f"icp_relevance {m['icp_relevance']} < {t['icp_relevance_min']}")
    if m["contactable_rate"] < t["contactable_min"]:
        failed.append(f"contactable_rate {m['contactable_rate']} < {t['contactable_min']}")
    return "recommend: accept" if not failed else "recommend: reject (" + "; ".join(failed) + ")"


def write_report(source_id: str, segment: str) -> tuple[Path, dict, str]:
    m = metrics(source_id, segment)
    v = verdict(m)
    t = protocol()["thresholds"]
    lines = [f"# Source validation — {source_id} × {segment}", "",
             f"Thresholds (set {protocol()['set_on']}, before data): icp_relevance ≥ {t['icp_relevance_min']}, "
             f"contactable ≥ {t['contactable_min']}", "", "| metric | value |", "|---|---|"]
    lines += [f"| {k} | {val} |" for k, val in m.items()]
    lines += ["", f"**Verdict:** {v}", "",
              "Rates over all ingested records for this segment; icp_relevance over the hand-labelled sample only."]
    out = SAMPLES / f"{source_id}__{segment}__report.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out, m, v
