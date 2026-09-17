"""Stage 1 — build Apify actor inputs from config/queries.yaml (inputs are committed for reproducibility).

  uv run python scripts/01_build_apify_inputs.py google_maps --mode full
  uv run python scripts/01_build_apify_inputs.py google_maps --mode sample

Full mode refuses to write inputs if the upper-bound cost exceeds the remaining budget
(budget_usd - spent_usd). Paste a file into the actor's JSON input in Apify Console,
export the dataset (All fields, JSON) to data/raw/google_maps/<YYYY-MM-DD>__<label>.json,
ingest it, and fill cost in data/runs.csv.
"""
import argparse
import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from ksa_pipeline.paths import APIFY_INPUTS, CONFIG  # noqa: E402


def write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {path.relative_to(APIFY_INPUTS.parents[1])}")


def circle(city: dict) -> dict:
    # GeoJSON order is [longitude, latitude] — the opposite of what Google Maps displays
    return {"type": "Point", "coordinates": [city["lng"], city["lat"]], "radiusKm": city["radius_km"]}


def payload(gm: dict, keywords: list[str], city: dict, max_places: int, contacts: bool) -> dict:
    return {**gm["actor_defaults"], "scrapeContacts": contacts, "searchStringsArray": keywords,
            "customGeolocation": circle(city), "maxCrawledPlacesPerSearch": max_places}


def google_maps(q: dict, mode: str) -> None:
    gm = q["google_maps"]
    if mode == "sample":
        city = gm["sample"]["city"]
        for segment, lists in gm["segments"].items():
            write(APIFY_INPUTS / "sample" / f"google_maps__{segment}__{city}.json",
                  payload(gm, lists["keywords"][:1], q["cities"][city], gm["sample"]["max_places"], False))
        return

    for stale in (APIFY_INPUTS / "full").glob("google_maps__*.json"):
        stale.unlink()   # inputs from an older plan must not be run by mistake

    plan, total_places, total_cost = [], 0, 0.0
    for segment, cfg in gm["full"]["segments"].items():
        keywords = gm["segments"][segment]["keywords"]
        price_1k = gm["price_per_1k_places_usd"] + (gm["contacts_per_1k_usd"] if cfg["scrapeContacts"] else 0)
        for city in gm["full"]["cities"]:
            places = len(keywords) * cfg["max_places"]
            cost = places * price_1k / 1000
            total_places += places
            total_cost += cost
            plan.append((segment, city, keywords, cfg))
            print(f"  {segment:20} {city:8} {len(keywords)} kw x {cfg['max_places']} = {places:>3} places x ${price_1k:.2f}/1K = ${cost:.2f}")

    remaining = gm["budget_usd"] - gm["spent_usd"]
    print(f"full plan: up to {total_places} places, up to ${total_cost:.2f} (remaining budget ${remaining:.2f}; upper bound)")
    if total_cost > remaining:
        sys.exit("OVER BUDGET - no inputs written. Lower max_places or cut keywords in config/queries.yaml.")

    for segment, city, keywords, cfg in plan:
        write(APIFY_INPUTS / "full" / f"google_maps__{segment}__{city}.json",
              payload(gm, keywords, q["cities"][city], cfg["max_places"], cfg["scrapeContacts"]))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("source", choices=["google_maps"])
    ap.add_argument("--mode", choices=["sample", "full"], default="full")
    args = ap.parse_args()
    google_maps(yaml.safe_load((CONFIG / "queries.yaml").read_text(encoding="utf-8")), args.mode)
