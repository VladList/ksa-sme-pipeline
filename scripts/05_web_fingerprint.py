"""Stage 5 — fetch merchant homepages, detect BNPL providers and contacts.

  uv run python scripts/05_web_fingerprint.py --probe https://example.sa [...]   # step 4.1: markers on known pages
  uv run python scripts/05_web_fingerprint.py --run --limit 20                  # step 4.2: trial on 20 pages
  uv run python scripts/05_web_fingerprint.py --run                             # step 4.2: all eligible merchants

--refresh ignores the cache (data/cache/web/, not committed); --workers sets parallel fetches (default 8).
--run writes data/interim/bnpl.csv (not committed), data/samples/bnpl_summary.md and data/samples/C_contact_check.csv.
Rows of C_contact_check.csv with checked_by=manual_browser are kept on re-runs.

  uv run python scripts/05_web_fingerprint.py --manual-c    # opens each blocked C sample store, asks y/n, saves per store
"""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from ksa_pipeline.bnpl import context, detect, discover  # noqa: E402
from ksa_pipeline.web import fetch  # noqa: E402


def probe(urls: list[str], refresh: bool) -> None:
    for url in urls:
        page = fetch(url, use_cache=not refresh)
        print(f"\n=== {url}")
        print(f"status {page['status']} ok={page['ok']} final={page['final_url']} {page['error']} | html {len(page['html'])} chars")
        if not page["ok"]:
            continue
        d = detect(page["html"])
        print(f"bnpl_status: {d['bnpl_status']} | providers: {d['providers']} | evidence: {d['evidence']}")
        for ev in d["evidence"]:
            provider, kind, needle = ev.split(":", 2)
            word = kind in ("text_ar", "text_en") and provider != "generic_installment"
            for snip in context(page["html"], needle, word=word):
                print(f"   [{ev[:80]}] …{snip}…")
        found = discover(page["html"])
        print("attributes mentioning a provider:" + ("" if found else " none"))
        for v in found:
            print(f"   {v}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--probe", nargs="+", metavar="URL")
    mode.add_argument("--run", action="store_true", help="all eligible merchants from data/interim/merchants.csv")
    mode.add_argument("--manual-c", action="store_true", help="check by hand the C sample stores the script could not load")
    ap.add_argument("--limit", type=int, help="with --run: fetch only the first N pages (trial, not a result)")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--refresh", action="store_true", help="ignore the cache and fetch again")
    args = ap.parse_args()
    if args.probe:
        probe(args.probe, args.refresh)
    elif args.manual_c:
        from ksa_pipeline.fingerprint import manual_c_check  # noqa: E402
        manual_c_check()
    else:
        from ksa_pipeline.fingerprint import run  # noqa: E402
        started = time.time()
        out = run(workers=args.workers, refresh=args.refresh, limit=args.limit)
        print(out["summary"])
        print(f"{len(out['rows'])} merchants in {time.time() - started:.0f}s -> data/interim/bnpl.csv, "
              "data/samples/bnpl_summary.md" + ("" if args.limit is not None else ", data/samples/C_contact_check.csv"))
