"""Guard: no unmasked Saudi mobile numbers in committed files (wired into pre-commit)."""
from __future__ import annotations

import re
from pathlib import Path

from .normalize import to_ascii_digits

# Separators inside one phone number: spaces, tabs, dashes, dots, brackets — never a line break,
# otherwise a digit at the end of one CSV row glues onto the date that starts the next row.
_JOIN_SEPARATORS = re.compile(r"(?<=\d)[ \t\-.()]+(?=\d)")
_ISO_DATE = re.compile(r"(?<!\d)\d{4}-\d{2}-\d{2}(?!\d)")
_KSA_MOBILE = re.compile(r"(?<!\d)(?:\+?966|00966|0)?5\d{8}(?!\d)")


def find_mobiles(text: str) -> list[str]:
    text = _ISO_DATE.sub(" DATE ", to_ascii_digits(text))
    return _KSA_MOBILE.findall(_JOIN_SEPARATORS.sub("", text))


def scan(paths: list[Path]) -> dict[str, int]:
    hits = {}
    for p in paths:
        if p.suffix.lower() not in {".csv", ".md", ".yaml", ".yml", ".json", ".txt"}:
            continue
        n = len(find_mobiles(p.read_text(encoding="utf-8", errors="ignore")))
        if n:
            hits[str(p)] = n
    return hits
