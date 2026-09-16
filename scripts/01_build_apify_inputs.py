"""Stage 1 — build Apify actor inputs from config/queries.yaml (inputs are committed for reproducibility).

  uv run python scripts/01_build_apify_inputs.py google_maps --mode sample
  uv run python scripts/01_build_apify_inputs.py google_maps --mode full
  uv run python scripts/01_build_apify_inputs.py instagram --segment A_aesthetic_clinics   # handles from ingested Maps rows

Paste a file into the actor's JSON input in Apify Console (or call the API),
export the dataset as JSON to data/raw/<source_id>/<YYYY-MM-DD>__<label>.json,
and add a row to data/runs.csv (cost from the Apify run page).
"""
import argparse
import csv
import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from ksa_pipeline.paths import APIFY_INPUTS, CONFIG, INTERIM  # noqa: E402


def write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {path.relative_to(APIFY_INPUTS.parents[1])}")


def google_maps(q: dict, mode: str) -> None:
    gm = q["google_maps"]
    for segment, langs in gm["segments"].items():
        if mode == "sample":
            city = gm["sample"]["city"]
            payload = {**gm["actor_defaults"], "searchStringsArray": [langs["ar"][0]],
                       "locationQuery": q["cities"][city], "maxCrawledPlacesPerSearch": gm["sample"]["max_places"]}
            write(APIFY_INPUTS / "sample" / f"google_maps__{segment}__{city}.json", payload)
        else:
            for city, location in q["cities"].items():
                payload = {**gm["actor_defaults"], "searchStringsArray": langs.get("ar", []) + langs.get("en", []),
                           "locationQuery": location, "maxCrawledPlacesPerSearch": gm["full"]["max_places"]}
                write(APIFY_INPUTS / "full" / f"google_maps__{segment}__{city}.json", payload)


def instagram(segment: str) -> None:
    handles = set()
    for path in sorted((INTERIM / "google_maps").glob("*.csv")):
        with path.open(encoding="utf-8") as f:
            handles |= {r["instagram_handle"] for r in csv.DictReader(f) if r["segment"] == segment and r["instagram_handle"]}
    if not handles:
        sys.exit(f"no instagram handles for {segment} in data/interim/google_maps/ — ingest Maps first")
    write(APIFY_INPUTS / "full" / f"instagram_profiles__{segment}.json", {"usernames": sorted(handles)})


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("source", choices=["google_maps", "instagram"])
    ap.add_argument("--mode", choices=["sample", "full"], default="sample")
    ap.add_argument("--segment")
    args = ap.parse_args()
    queries = yaml.safe_load((CONFIG / "queries.yaml").read_text(encoding="utf-8"))
    if args.source == "google_maps":
        google_maps(queries, args.mode)
    else:
        if not args.segment:
            sys.exit("--segment is required for instagram")
        instagram(args.segment)
