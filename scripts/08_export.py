"""Step 5.3 — export the scored list.

  uv run python scripts/08_export.py              # masked: output/public/*.csv and ksa_sme_pipeline.xlsx
  uv run python scripts/08_export.py --private    # also data/private/top50_contacts.csv with real numbers (not committed)

The masked export fails before writing if any value still contains an unmasked KSA mobile number.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from ksa_pipeline.export import run  # noqa: E402

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--private", action="store_true", help="also write data/private/top50_contacts.csv with real numbers")
    args = ap.parse_args()
    out = run(private=args.private)
    print(f"{out['merchants']} merchants, Top-{out['top']}")
    for f in out["files"]:
        print(" ", f)
