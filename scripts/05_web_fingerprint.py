"""Stage 5 — fetch merchant websites and detect BNPL providers.

Step 4.1 (verify markers on known pages before trusting them):
  uv run python scripts/05_web_fingerprint.py --probe https://example.sa https://salla.sa/store

Prints, per URL: fetch status, detected providers with the text around each marker, and every attribute value on the
page that mentions a provider (to spot markers the config does not know yet). Pages are cached in data/cache/web/.
"""
import argparse
import sys
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
    ap.add_argument("--probe", nargs="+", metavar="URL", required=True)
    ap.add_argument("--refresh", action="store_true", help="ignore the cache and fetch again")
    args = ap.parse_args()
    probe(args.probe, args.refresh)
