"""Check exclusion rules against labels already in data/samples/ (counts only, safe to commit).

in_sample = the rule was written after these labels were seen, so its accuracy there is optimistic.
"""
from __future__ import annotations

import csv
from pathlib import Path

from . import paths
from .rules import exclusion_reasons

LABEL_SETS = [
    # segment, file, row filter, name col, category col, label col, in_sample, note
    ("A_aesthetic_clinics", "google_maps__keyword_probe_A_circle__labeling.csv", None, "name", "category", "fit", True, "probe, Riyadh circle"),
    ("A_aesthetic_clinics", "google_maps__A_aesthetic_clinics__sample.csv", None, "name", "category_raw", "icp_label", True, "full-run validation sample"),
    ("B_custom_furniture", "google_maps__keyword_probe__labeling.csv", ("segment", "B"), "name", "category", "fit", False, "probe (labelled before the rule existed)"),
    ("B_custom_furniture", "google_maps__B_custom_furniture__sample.csv", None, "name", "category_raw", "icp_label", True, "full-run validation sample (rule fitted here)"),
    ("C_salla_zid_d2c", "salla_zid_dork__C_salla_zid_d2c__sample.csv", None, "name", None, "icp_label", True, "validation sample"),
]


def evaluate() -> list[dict]:
    results = []
    for segment, filename, row_filter, name_col, cat_col, label_col, in_sample, note in LABEL_SETS:
        path = paths.SAMPLES / filename
        if not path.exists():
            continue
        c = {"kept_fit": 0, "dropped_fit": 0, "kept_not_fit": 0, "dropped_not_fit": 0}
        with path.open(encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if row_filter and r.get(row_filter[0]) != row_filter[1]:
                    continue
                label = (r.get(label_col) or "").strip()
                if label not in ("fit", "not_fit"):
                    continue
                cats = {r[cat_col]} if cat_col and r.get(cat_col) else set()
                kept = not exclusion_reasons(segment, r.get(name_col) or "", cats, r.get("store_key") or "")
                c[f"{'kept' if kept else 'dropped'}_{label}"] += 1
        kept = c["kept_fit"] + c["kept_not_fit"]
        fit = c["kept_fit"] + c["dropped_fit"]
        results.append({"segment": segment, "file": filename, "note": note, "in_sample": in_sample, **c,
                        "precision_of_kept": round(c["kept_fit"] / kept, 2) if kept else None,
                        "fit_retained": round(c["kept_fit"] / fit, 2) if fit else None})
    return results


def write_report(results: list[dict]) -> Path:
    lines = ["# Exclusion rules vs existing labels", "",
             "Rules: `config/rules.yaml`. Labels: files in `data/samples/`; `unclear` rows are ignored.",
             "`precision_of_kept` = fit / (fit + not_fit) among records the rules keep; "
             "`fit_retained` = share of fit records the rules keep.",
             "**in-sample** = rule written after seeing these labels (optimistic).", "",
             "| segment | label set | in-sample | kept fit | dropped fit | kept not_fit | dropped not_fit | precision of kept | fit retained |",
             "|---|---|---|---|---|---|---|---|---|"]
    for r in results:
        lines.append(f"| {r['segment']} | {r['note']} | {'yes' if r['in_sample'] else '**no**'} | {r['kept_fit']} | {r['dropped_fit']} | "
                     f"{r['kept_not_fit']} | {r['dropped_not_fit']} | {r['precision_of_kept']} | {r['fit_retained']} |")
    out = paths.SAMPLES / "rules_check.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out
