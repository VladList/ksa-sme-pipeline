"""Source validation: fill rates on ingested runs + ICP relevance on a hand-labelled sample.

Thresholds come from data/sources.yaml (validation_protocol), fixed before data.
Runs are selected with a glob on run_id (e.g. "2026-09-17__full_*") so probe runs
with a different location setup do not distort the metrics. The sample is stratified
by run (equal share per run, i.e. per city), and every metric is also reported per run.
The verdict is a recommendation; changing status in sources.yaml stays a manual, dated decision.
"""
from __future__ import annotations

import csv
import random
from collections import defaultdict
from pathlib import Path

import yaml

from . import paths
from .normalize import mask_phone


def protocol() -> dict:
    return yaml.safe_load(paths.SOURCES_YAML.read_text(encoding="utf-8"))["validation_protocol"]


def chain_threshold() -> int:
    return yaml.safe_load((paths.CONFIG / "icp.yaml").read_text(encoding="utf-8"))["disqualifiers"]["chain_location_threshold"]


def load_interim(source_id: str, segment: str, runs: str = "*") -> list[dict]:
    rows, seen = [], set()
    for path in sorted((paths.INTERIM / source_id).glob(f"{runs}.csv")):
        with path.open(encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r["segment"] == segment and r["record_id"] not in seen:   # same place in two runs counted once
                    seen.add(r["record_id"])
                    rows.append(r)
    return rows


def sample_path(source_id: str, segment: str) -> Path:
    return paths.SAMPLES / f"{source_id}__{segment}__sample.csv"


def make_sample(source_id: str, segment: str, runs: str = "*") -> Path:
    p = protocol()
    by_run = defaultdict(list)
    for r in load_interim(source_id, segment, runs):
        by_run[r["run_id"]].append(r)
    if not by_run:
        raise SystemExit(f"no ingested rows for {source_id} {segment} matching runs '{runs}'")
    rng = random.Random(p["random_seed"])
    run_ids = sorted(by_run)
    base, extra = divmod(p["sample_size"], len(run_ids))
    picked = []
    for i, run_id in enumerate(run_ids):
        k = min(base + (1 if i < extra else 0), len(by_run[run_id]))
        picked += rng.sample(by_run[run_id], k)
    fields = ["record_id", "run_id", "name", "category_raw", "city", "phone_masked", "phone_type",
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


def fill_metrics(rows: list[dict]) -> dict:
    chain_t = chain_threshold()
    return {
        "n_records": len(rows),
        "fill_phone_any": _rate(rows, lambda r: r["phone_e164"]),
        "fill_phone_mobile": _rate(rows, lambda r: r["phone_type"] == "mobile"),
        "fill_own_site": _rate(rows, lambda r: r["website_platform"] == "own_site"),
        "fill_instagram": _rate(rows, lambda r: r["instagram_handle"]),
        "contactable_rate": _rate(rows, lambda r: r["phone_type"] == "mobile" or r["instagram_handle"] or r["has_whatsapp_link"] == "True"),
        "closed_rate": _rate(rows, lambda r: r["is_closed"] == "True"),
        "chain_rate": _rate(rows, lambda r: r["name_location_count"] and int(r["name_location_count"]) > chain_t),
    }


def label_metrics(labels: list[str]) -> dict:
    labeled = [l for l in labels if l]
    return {
        "sample_size": len(labels), "labeled": len(labeled),
        "fit": labeled.count("fit"), "not_fit": labeled.count("not_fit"), "unclear": labeled.count("unclear"),
        "icp_relevance": round(labeled.count("fit") / len(labeled), 3) if labeled else None,
    }


def metrics(source_id: str, segment: str, runs: str = "*") -> tuple[dict, dict]:
    rows = load_interim(source_id, segment, runs)
    sample = []
    sp = sample_path(source_id, segment)
    if sp.exists():
        with sp.open(encoding="utf-8") as f:
            sample = list(csv.DictReader(f))
    overall = {**fill_metrics(rows), **label_metrics([s["icp_label"].strip() for s in sample])}
    per_run = {}
    for run_id in sorted({r["run_id"] for r in rows}):
        per_run[run_id] = {**fill_metrics([r for r in rows if r["run_id"] == run_id]),
                           **label_metrics([s["icp_label"].strip() for s in sample if s.get("run_id") == run_id])}
    return overall, per_run


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


def write_report(source_id: str, segment: str, runs: str = "*") -> tuple[Path, dict, dict, str]:
    overall, per_run = metrics(source_id, segment, runs)
    v = verdict(overall)
    t = protocol()["thresholds"]
    run_ids = list(per_run)
    lines = [f"# Source validation — {source_id} × {segment}", "",
             f"Runs included (glob `{runs}`): " + ", ".join(f"`{r}`" for r in run_ids), "",
             f"Thresholds (set {protocol()['set_on']}, before data): icp_relevance ≥ {t['icp_relevance_min']}, "
             f"contactable ≥ {t['contactable_min']}", "",
             "| metric | all | " + " | ".join(r.split("__")[-1] for r in run_ids) + " |",
             "|---|---|" + "---|" * len(run_ids)]
    for k in overall:
        lines.append(f"| {k} | {overall[k]} | " + " | ".join(str(per_run[r][k]) for r in run_ids) + " |")
    lines += ["", f"**Verdict:** {v}", "",
              "Fill rates over all ingested records of the included runs; icp_relevance over the hand-labelled sample, "
              "stratified equally per run."]
    out = paths.SAMPLES / f"{source_id}__{segment}__report.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out, overall, per_run, v
