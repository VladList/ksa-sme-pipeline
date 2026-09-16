"""Stage 2 — raw export -> canonical CSV in data/interim/<source_id>/<run_id>.csv.

  uv run python scripts/02_ingest.py google_maps data/raw/google_maps/2026-09-16__sample_A.json
  uv run python scripts/02_ingest.py instagram  data/raw/instagram/2026-09-16__A.json --segment A_aesthetic_clinics
  uv run python scripts/02_ingest.py salla_zid_dork data/raw/salla_zid_dork/2026-09-16__dork.csv

data/raw is never modified. Re-running overwrites only the interim file for that run.
"""
import argparse
import csv
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from ksa_pipeline.ingest import ADAPTERS, ingest, write_csv  # noqa: E402
from ksa_pipeline.paths import INTERIM, ROOT, RUNS_CSV  # noqa: E402


def upsert_run(run_id: str, source_id: str, raw: Path, n: int) -> None:
    with RUNS_CSV.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fields, rows = reader.fieldnames, list(reader)
    existing = next((r for r in rows if r["run_id"] == run_id), None)
    if existing:
        existing["n_records"] = str(n)
    else:
        rows.append({"run_id": run_id, "source_id": source_id, "raw_file": str(raw.relative_to(ROOT)), "n_records": str(n)})
        print("  -> add actor, input_file, cost_usd, ran_on to data/runs.csv by hand")
    with RUNS_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("source", choices=sorted(ADAPTERS))
    ap.add_argument("raw", type=Path)
    ap.add_argument("--segment", help="segment for rows the adapter cannot infer from the query")
    args = ap.parse_args()
    raw = args.raw.resolve()
    rows = ingest(args.source, raw, args.segment)
    out = INTERIM / args.source / f"{raw.stem}.csv"
    write_csv(rows, out)
    upsert_run(raw.stem, args.source, raw, len(rows))
    print(f"{len(rows)} records -> {out.relative_to(ROOT)}")
    print("  segments:", dict(Counter(r["segment"] for r in rows)))
    print("  phone_type:", dict(Counter(r["phone_type"] for r in rows)))
    print("  website_platform:", dict(Counter(r["website_platform"] for r in rows)))
    missing = sum(1 for r in rows if not r["segment"])
    if missing:
        print(f"  WARNING: {missing} rows without segment — pass --segment or add the query to config/queries.yaml")
