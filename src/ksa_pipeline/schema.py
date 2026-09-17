"""Loads config/schema.yaml — the single source of column names, order and PII flags."""
from __future__ import annotations

from functools import lru_cache

import yaml

from .paths import CONFIG


@lru_cache
def load_schema() -> list[dict]:
    return yaml.safe_load((CONFIG / "schema.yaml").read_text(encoding="utf-8"))["columns"]


def columns(stage: str = "ingest") -> list[str]:
    return [c["name"] for c in load_schema() if c["stage"] == stage]


def merchant_columns() -> list[dict]:
    return yaml.safe_load((CONFIG / "schema.yaml").read_text(encoding="utf-8"))["merchant_columns"]


def web_columns() -> list[dict]:
    return yaml.safe_load((CONFIG / "schema.yaml").read_text(encoding="utf-8"))["web_columns"]


def enrich_columns() -> list[dict]:
    return yaml.safe_load((CONFIG / "schema.yaml").read_text(encoding="utf-8"))["enrich_columns"]


def scored_columns() -> list[dict]:
    return yaml.safe_load((CONFIG / "schema.yaml").read_text(encoding="utf-8"))["scored_columns"]


def pii_columns() -> set[str]:
    return {c["name"] for c in load_schema() if c.get("pii")}


def contract_violations() -> list[str]:
    """Rules the contract holds itself to (checked in tests, so they cannot drift)."""
    problems = []
    names = [c["name"] for c in load_schema()]
    if len(names) != len(set(names)):
        problems.append("duplicate column names")
    for c in load_schema() + enrich_columns():
        if c.get("origin") == "llm" and not c["name"].endswith("_inferred"):
            problems.append(f"{c['name']}: LLM-derived column must end with _inferred")
    return problems
