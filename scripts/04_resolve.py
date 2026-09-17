"""Stage 4 — records -> merchants (entity resolution) + exclusion rules + rule check against labels.

  uv run python scripts/04_resolve.py

Reads   data/interim/<source>/<run>.csv for the inputs listed in config/rules.yaml
Writes  data/interim/merchants.csv          (not committed: contains phones)
        data/samples/resolve_summary.md     (counts only, committed)
        data/samples/rules_check.md         (rules vs existing labels, committed)
"""
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from ksa_pipeline import paths  # noqa: E402
from ksa_pipeline.resolve import load_records, resolve, write_merchants  # noqa: E402
from ksa_pipeline.rules_check import evaluate, write_report  # noqa: E402


def main() -> None:
    records = load_records()
    merchants, stats = resolve(records)
    write_merchants(merchants)

    hubs = Counter(v.split(":", 1)[0] for v in stats["hub_identifiers_ignored"])
    lines = ["# Entity resolution and exclusions", "",
             f"- records in: {stats['records']}",
             f"- merchants out: {stats['merchants']} ({stats['merged_groups']} merchants built from 2+ records)",
             f"- identifiers ignored as hubs (shared by too many records): {dict(hubs) or 'none'}", "",
             "## Merchants by segment", "",
             "| segment | merchants | excluded | eligible | eligible contactable |", "|---|---|---|---|---|"]
    for seg in sorted({m["segment"] for m in merchants}):
        ms = [m for m in merchants if m["segment"] == seg]
        el = [m for m in ms if not m["exclusion_reason"]]
        lines.append(f"| {seg} | {len(ms)} | {len(ms) - len(el)} | {len(el)} | {sum(m['contactable'] for m in el)} |")
    lines += ["", "## Eligible merchants by segment and city", "", "| segment | city | eligible |", "|---|---|---|"]
    for (seg, city), n in sorted(Counter((m["segment"], m["cities"] or "n/a") for m in merchants if not m["exclusion_reason"]).items()):
        lines.append(f"| {seg} | {city} | {n} |")
    lines += ["", "## Exclusion reasons", "", "| segment | reason | merchants |", "|---|---|---|"]
    reason_counts = Counter((m["segment"], r) for m in merchants for r in m["exclusion_reason"].split("; ") if r)
    for (seg, reason), n in sorted(reason_counts.items()):
        lines.append(f"| {seg} | {reason} | {n} |")
    summary = paths.SAMPLES / "resolve_summary.md"
    summary.write_text("\n".join(lines) + "\n", encoding="utf-8")

    check = write_report(evaluate())
    print("\n".join(lines))
    print(f"\nwrote {paths.INTERIM.relative_to(paths.ROOT)}/merchants.csv, {summary.relative_to(paths.ROOT)}, {check.relative_to(paths.ROOT)}")
    print(check.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
