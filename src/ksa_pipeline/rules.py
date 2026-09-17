"""Exclusion rules from config/rules.yaml, applied to one merchant (or one labelled record)."""
from __future__ import annotations

import re
from functools import lru_cache

import yaml

from . import paths


@lru_cache
def load_rules() -> dict:
    return yaml.safe_load((paths.CONFIG / "rules.yaml").read_text(encoding="utf-8"))


@lru_cache
def chain_threshold() -> int:
    return yaml.safe_load((paths.CONFIG / "icp.yaml").read_text(encoding="utf-8"))["disqualifiers"]["chain_location_threshold"]


def _rx(pattern: str) -> re.Pattern:
    return re.compile(pattern, re.IGNORECASE)


def exclusion_reasons(segment: str, name: str, categories: set[str], store_key: str = "",
                      n_locations: int = 1, is_closed: bool = False) -> list[str]:
    """All reasons that exclude a merchant; empty list = eligible."""
    rules = load_rules()
    seg = rules["segments"].get(segment, {})
    name = name or ""
    reasons = []
    if rules["common"]["exclude_closed"] and is_closed:
        reasons.append("closed")
    if n_locations > chain_threshold():
        reasons.append(f"chain: {n_locations} locations")
    keep = seg.get("keep_if_signal")
    if keep and not (_rx(keep["name_regex"]).search(name) or categories & set(keep["categories"])):
        reasons.append(f"{segment[0]}: no segment signal in name or category")
    exc = seg.get("exclude_if", {})
    if categories & set(exc.get("categories", [])) or ("name_regex" in exc and _rx(exc["name_regex"]).search(name)):
        reasons.append(f"{segment[0]}: hospital or enterprise group")
    text = f"{name} {store_key or ''}"
    if "outside_ksa_regex" in exc and _rx(exc["outside_ksa_regex"]).search(text):
        reasons.append("C: outside KSA signal")
    if "wholesale_regex" in exc and _rx(exc["wholesale_regex"]).search(text):
        reasons.append("C: wholesale")
    return reasons
