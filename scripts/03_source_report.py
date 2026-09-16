"""Stage 3 — validate a source per segment (Day 1 "drop invalid sources" step, with numbers).

  uv run python scripts/03_source_report.py sample google_maps A_aesthetic_clinics
      -> data/samples/google_maps__A_aesthetic_clinics__sample.csv   (label icp_label by hand: fit | not_fit | unclear)
  uv run python scripts/03_source_report.py report google_maps A_aesthetic_clinics
      -> data/samples/google_maps__A_aesthetic_clinics__report.md    (metrics + recommendation)

Then update status in data/sources.yaml by hand, with the date and the reason.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from ksa_pipeline.paths import ROOT  # noqa: E402
from ksa_pipeline.validation import make_sample, write_report  # noqa: E402

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["sample", "report"])
    ap.add_argument("source")
    ap.add_argument("segment")
    args = ap.parse_args()
    if args.action == "sample":
        print("wrote", make_sample(args.source, args.segment).relative_to(ROOT))
    else:
        path, m, v = write_report(args.source, args.segment)
        for k, val in m.items():
            print(f"  {k:20} {val}")
        print(f"  {v}\nwrote {path.relative_to(ROOT)}")
