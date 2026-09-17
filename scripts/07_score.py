"""Phase 5 — score merchants, assign tiers, build the Top-50 and test its sensitivity.

  uv run python scripts/07_score.py

Reads data/interim/merchants.csv, bnpl.csv, enrich.csv, data/samples/bnpl_tabby_qa.csv, config/icp.yaml, config/scoring.yaml.
Writes data/interim/scored.csv (not committed) and data/samples/scoring_summary.md (counts only).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from ksa_pipeline.scoring import run  # noqa: E402

if __name__ == "__main__":
    print(run()["summary"])
