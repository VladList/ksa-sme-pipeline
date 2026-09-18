"""Packaging check — scan the whole git history, not just the working tree, before making the repository public.

  uv run python scripts/09_check_history.py

Walks every blob in every commit and reports unmasked KSA mobile numbers (data/private and .env never were committed,
but a file can have been staged once by mistake) and anything that looks like an API key. Exits non-zero on a hit.
"""
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from ksa_pipeline.pii import find_mobiles  # noqa: E402

SECRET = re.compile(r"sk-[A-Za-z0-9_-]{20,}|ghp_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|apify_api_[A-Za-z0-9]{20,}")
MAX_BYTES = 2_000_000
# Test doubles used across the test suite and fixtures; never a real subscriber number (5 5000 00xx family plus two dummies).
SYNTHETIC = {"550000001", "550000002", "550000004", "550000123", "551234567", "512345678"}


def national(number: str) -> str:
    digits = re.sub(r"\D", "", number)
    for prefix in ("00966", "966"):
        if digits.startswith(prefix):
            digits = digits[len(prefix):]
    return digits.lstrip("0")


def blobs() -> list[tuple[str, str]]:
    """Every blob (not tree) reachable from any commit, with the path it was stored under."""
    listed = subprocess.run(["git", "rev-list", "--objects", "--all"], capture_output=True, text=True, check=True).stdout
    pairs = [(line.split(" ", 1)[0], line.split(" ", 1)[1]) for line in listed.splitlines() if " " in line]
    check = subprocess.run(["git", "cat-file", "--batch-check"], input="\n".join(sha for sha, _ in pairs),
                           capture_output=True, text=True, check=True).stdout.split("\n")
    kinds = {line.split(" ")[0]: line.split(" ")[1] for line in check if len(line.split(" ")) > 2}
    return [(sha, path) for sha, path in pairs if kinds.get(sha) == "blob"]


if __name__ == "__main__":
    hits, objects = [], blobs()
    for sha, path in objects:
        if Path(path).suffix.lower() not in {".csv", ".md", ".yaml", ".yml", ".json", ".txt", ".py", ".toml", ".example", ""}:
            continue
        raw = subprocess.run(["git", "cat-file", "-p", sha], capture_output=True, check=False).stdout[:MAX_BYTES]
        text = raw.decode("utf-8", errors="ignore")
        mobiles = [m for m in find_mobiles(text) if national(m) not in SYNTHETIC]
        secrets = SECRET.findall(text)
        if mobiles:
            hits.append(f"{path} ({sha[:8]}): {len(mobiles)} unmasked KSA mobile number(s)")
        if secrets:
            hits.append(f"{path} ({sha[:8]}): {len(secrets)} secret-looking token(s)")
    print(f"scanned {len(objects)} blobs in the full history (test doubles {sorted(SYNTHETIC)} allowed)")
    for h in hits:
        print("HIT:", h)
    print("clean: nothing found" if not hits else f"{len(hits)} problem(s) found")
    sys.exit(1 if hits else 0)
