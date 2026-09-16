"""Pre-commit guard: fail if a staged text file contains an unmasked Saudi mobile number."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from ksa_pipeline.pii import scan  # noqa: E402

if __name__ == "__main__":
    hits = scan([Path(p) for p in sys.argv[1:]])
    for path, n in hits.items():
        print(f"PII: {n} unmasked KSA mobile number(s) in {path}")
    sys.exit(1 if hits else 0)
