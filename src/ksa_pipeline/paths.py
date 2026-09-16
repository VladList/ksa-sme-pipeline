from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "config"
DATA = ROOT / "data"
RAW = DATA / "raw"
INTERIM = DATA / "interim"
SAMPLES = DATA / "samples"
APIFY_INPUTS = DATA / "apify_inputs"
RUNS_CSV = DATA / "runs.csv"
SOURCES_YAML = DATA / "sources.yaml"
