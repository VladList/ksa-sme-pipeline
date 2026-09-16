"""Guard: no unmasked Saudi mobile numbers in committed files (wired into pre-commit)."""
from __future__ import annotations

import re
from pathlib import Path

from .normalize import to_ascii_digits

_JOIN_SEPARATORS = re.compile(r"(?<=\d)[\s\-.()]+(?=\d)")
_KSA_MOBILE = re.compile(r"(?<!\d)(?:\+?966|00966|0)?5\d{8}(?!\d)")


def find_mobiles(text: str) -> list[str]:
    return _KSA_MOBILE.findall(_JOIN_SEPARATORS.sub("", to_ascii_digits(text)))


def scan(paths: list[Path]) -> dict[str, int]:
    hits = {}
    for p in paths:
        if p.suffix.lower() not in {".csv", ".md", ".yaml", ".yml", ".json", ".txt"}:
            continue
        n = len(find_mobiles(p.read_text(encoding="utf-8", errors="ignore")))
        if n:
            hits[str(p)] = n
    return hits
