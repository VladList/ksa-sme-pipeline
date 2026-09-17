"""Step 4.3 — LLM enrichment of eligible A and B merchants (owner name, ticket, Arabic opener; all `_inferred`).

  uv run python scripts/06_enrich.py --dry-run     # free: candidates, input size, rough input cost
  uv run python scripts/06_enrich.py --check       # free: is the configured model available for this key?
  uv run python scripts/06_enrich.py --trial       # config/llm.yaml trial.size merchants (seed 42): real cost + review
  uv run python scripts/06_enrich.py --run         # all candidates; cached answers are not paid again

Config: config/llm.yaml (model, prices, budget stop, prompt). Key: OPENAI_API_KEY in .env (never printed).
Writes data/interim/enrich_trial.csv or enrich.csv (not committed) and data/samples/enrich[_trial]_summary.md (counts).
"""
import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from ksa_pipeline import enrich, paths  # noqa: E402

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--trial", action="store_true")
    mode.add_argument("--run", action="store_true")
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()
    size = enrich.config()["trial"]["size"]
    if args.check:
        print(enrich.check_model())
    elif args.dry_run:
        print("all candidates:", enrich.run(dry_run=True))
        print("trial:", enrich.run(sample=size, dry_run=True))
    else:
        out = enrich.run(sample=size if args.trial else None, workers=args.workers)
        for k, v in out.items():
            print(f"{k}: {v}")
        if args.trial:
            rows = list(csv.DictReader((paths.INTERIM / "enrich_trial.csv").open(encoding="utf-8")))
            print("\n".join(enrich.review_lines(rows)))
