"""Entity resolution: ingested records -> merchants.

Records are linked when they share an identifier (place id, phone, own domain, Instagram handle, store key).
Identifiers shared by too many records are treated as noise, not links. One merchant = one sales conversation:
branches of one brand that share a phone, domain or handle become one merchant with n_locations > 1.
"""
from __future__ import annotations

import csv
import hashlib
from collections import Counter, defaultdict

from . import paths
from .rules import exclusion_reasons, load_rules
from .schema import merchant_columns

MERCHANT_COLUMNS = [c["name"] for c in merchant_columns()]          # contract: config/schema.yaml
PII_MERCHANT_COLUMNS = {c["name"] for c in merchant_columns() if c.get("pii")}


def load_records() -> list[dict]:
    rows, seen = [], set()
    for source_id, runs in load_rules()["inputs"].items():
        for path in sorted((paths.INTERIM / source_id).glob(f"{runs}.csv")):
            with path.open(encoding="utf-8") as f:
                for r in csv.DictReader(f):
                    if r["record_id"] not in seen:
                        seen.add(r["record_id"])
                        rows.append(r)
    return rows


class _UnionFind:
    def __init__(self, n: int):
        self.parent = list(range(n))

    def find(self, i: int) -> int:
        while self.parent[i] != i:
            self.parent[i] = self.parent[self.parent[i]]
            i = self.parent[i]
        return i

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[max(ra, rb)] = min(ra, rb)


def link_values(record: dict, identifier: str, ignore_domains: set[str]) -> list[str]:
    value = (record.get(identifier) or "").strip().lower()
    if not value:
        return []
    if identifier == "website_domain" and (value in ignore_domains or any(value.endswith("." + d) for d in ignore_domains)):
        return []
    return [f"{identifier}:{value}"]


def resolve(records: list[dict]) -> tuple[list[dict], dict]:
    cfg = load_rules()["link"]
    ignore = {d.lower() for d in cfg["ignore_domains"]}
    by_value = defaultdict(list)
    for i, r in enumerate(records):
        for ident in cfg["identifiers"]:
            for v in link_values(r, ident, ignore):
                by_value[v].append(i)

    uf = _UnionFind(len(records))
    hubs = {}
    for value, idx in by_value.items():
        if len(idx) > cfg["hub_max_records"]:
            hubs[value] = len(idx)
            continue
        for j in idx[1:]:
            uf.union(idx[0], j)
    for a, b in cfg.get("same_as", []):          # curated links with evidence in rules.yaml
        if by_value.get(a) and by_value.get(b):
            uf.union(by_value[a][0], by_value[b][0])

    groups = defaultdict(list)
    for i in range(len(records)):
        groups[uf.find(i)].append(records[i])

    merchants = [_merchant(members) for members in groups.values()]
    merchants.sort(key=lambda m: (m["segment"], m["exclusion_reason"] != "", m["name"] or ""))
    stats = {"records": len(records), "merchants": len(merchants),
             "merged_groups": sum(1 for g in groups.values() if len(g) > 1), "hub_identifiers_ignored": hubs}
    return merchants, stats


def _pick(members: list[dict], field: str) -> str:
    values = [m[field] for m in members if m.get(field)]
    return Counter(values).most_common(1)[0][0] if values else ""


def _merchant(members: list[dict]) -> dict:
    best = max(members, key=lambda m: int(float(m.get("reviews_count") or 0)))
    segment = Counter(m["segment"] for m in members).most_common(1)[0][0]
    phones = [m for m in members if m.get("phone_e164")]
    mobile = next((m for m in phones if m["phone_type"] == "mobile"), None)
    phone = mobile or (phones[0] if phones else {})
    places = {m["google_place_id"] for m in members if m.get("google_place_id")}
    categories = {m["category_raw"] for m in members if m.get("category_raw")}
    store_key = _pick(members, "store_key")
    instagram = _pick(members, "instagram_handle")
    cities = {m["run_id"].split("__")[-1] for m in members if m["source_id"] == "google_maps"}
    reasons = exclusion_reasons(segment, best.get("name") or "", categories, store_key,
                                n_locations=max(len(places), 1), is_closed=all(m.get("is_closed") == "True" for m in members),
                                n_cities=len(cities))
    record_ids = sorted(m["record_id"] for m in members)
    return {
        "merchant_id": "m_" + hashlib.sha1(record_ids[0].encode("utf-8")).hexdigest()[:10],
        "segment": segment,
        "cities": "|".join(sorted(cities)),
        "name": best.get("name") or "",
        "n_records": len(members),
        "n_locations": len(places),
        "sources": "|".join(sorted({m["source_id"] for m in members})),
        "categories": "|".join(sorted(categories)),
        "phone_e164": phone.get("phone_e164", ""),
        "phone_type": phone.get("phone_type", "none") if phone else "none",
        "website_domain": _pick(members, "website_domain"),
        "instagram_handle": instagram,
        "store_key": store_key,
        "evidence_url": best.get("evidence_url") or "",
        "rating": best.get("rating") or "",
        "reviews_count": sum(int(float(m.get("reviews_count") or 0)) for m in members),
        "contactable": bool(mobile or instagram or any(m.get("has_whatsapp_link") == "True" for m in members)),
        "exclusion_reason": "; ".join(reasons),
        "record_ids": "|".join(record_ids),
    }


def write_merchants(merchants: list[dict]) -> None:
    out = paths.INTERIM / "merchants.csv"
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=MERCHANT_COLUMNS, lineterminator="\n")
        w.writeheader()
        w.writerows(merchants)
