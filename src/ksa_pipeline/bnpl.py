"""BNPL detection on a fetched page, driven by config/bnpl_markers.yaml.

A homepage without markers is `not_detected`, never `none`: BNPL widgets often live on product or checkout
pages only, so absence on the homepage is not proof of absence.
Evidence entries are `provider:kind:marker` (kind = html | icon | text_ar | text_en), so counts can be split by kind.
"""
from __future__ import annotations

import re
from functools import lru_cache

import yaml

from . import paths

PROVIDER_NAMES = "tabby|tamara|madfu|mispay|emkan"
ATTR_RX = re.compile(r"""(?:src|href|data-[\w-]+|content)\s*=\s*["']([^"'\s<>]+)["']""", re.I)
IMAGE_EXT = r"(?:svg|png|webp|jpe?g|gif)"


@lru_cache
def markers() -> dict:
    return yaml.safe_load((paths.CONFIG / "bnpl_markers.yaml").read_text(encoding="utf-8"))


@lru_cache
def word_rx(term: str) -> re.Pattern:
    """Whole word, optional Arabic prefix و/ب/ل: matches 'وتابي', not 'كتابي'."""
    return re.compile(rf"(?<!\w)(?:[وبل])?{re.escape(term)}(?!\w)", re.I)


@lru_cache
def icon_rx(token: str) -> re.Pattern:
    return re.compile(rf"(?:^|[/_.\-]){re.escape(token)}[\w\-]*\.{IMAGE_EXT}(?:$|[?#])", re.I)


def attributes(html: str) -> list[str]:
    return ATTR_RX.findall(html or "")


def detect(html: str) -> dict:
    """Return {providers: [...], generic_installment: bool, evidence: [...], bnpl_status: str}."""
    cfg, html = markers(), html or ""
    low, attrs = html.lower(), attributes(html)
    found, evidence = [], []
    for name, m in cfg["providers"].items():
        hits = [f"html:{h}" for h in m.get("html", []) if h.lower() in low]
        for token in m.get("icon", []):
            hits += [f"icon:{v[:140]}" for v in dict.fromkeys(attrs) if icon_rx(token).search(v)][:2]
        if not m.get("ambiguous_ar"):
            hits += [f"text_ar:{t}" for t in m.get("text_ar", []) if word_rx(t).search(html)]
        if not m.get("ambiguous_en"):
            hits += [f"text_en:{t}" for t in m.get("text_en", []) if word_rx(t).search(html)]
        if hits:
            found.append(name)
            evidence += [f"{name}:{h}" for h in hits]
    generic = [t for t in cfg["generic_installment"]["text_ar"] if t in html]
    evidence += [f"generic_installment:text_ar:{t}" for t in generic]
    status, _ = status_from_evidence(evidence)
    return {"providers": found, "generic_installment": bool(generic), "evidence": evidence, "bnpl_status": status}


def status_from_evidence(evidence: list[str]) -> tuple[str, list[str]]:
    """Status and providers from `provider:kind:marker` entries (used again after platform-template evidence is dropped)."""
    providers = list(dict.fromkeys(e.split(":", 1)[0] for e in evidence if not e.startswith("generic_installment:")))
    if "tabby" in providers:
        return "tabby", providers
    if providers:
        return "competitor_only", providers
    if any(e.startswith("generic_installment:") for e in evidence):
        return "generic_installment", providers
    return "not_detected", providers


def discover(html: str, limit: int = 12) -> list[str]:
    """Attribute values that mention a BNPL provider: used to confirm or correct the markers on live pages."""
    rx = re.compile(PROVIDER_NAMES, re.I)
    return [v[:140] for v in dict.fromkeys(attributes(html)) if rx.search(v)][:limit]


def context(html: str, needle: str, width: int = 60, limit: int = 2, word: bool = False) -> list[str]:
    """Snippets around a marker, with long digit runs masked (pages carry phone numbers)."""
    rx = word_rx(needle) if word else re.compile(re.escape(needle), re.I)
    out = []
    for m in rx.finditer(html or ""):
        snippet = re.sub(r"\s+", " ", html[max(0, m.start() - width): m.end() + width])
        out.append(re.sub(r"\d{7,}", "•••", snippet))
        if len(out) >= limit:
            break
    return out
