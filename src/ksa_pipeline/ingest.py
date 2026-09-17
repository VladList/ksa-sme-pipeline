"""Adapters: raw vendor export (immutable, data/raw/) -> canonical rows (config/schema.yaml).

One adapter per source_id. Adapters never drop rows — filtering happens on Day 2
and is recorded as exclusion_reason, so every raw record stays traceable.
"""
from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Callable, Iterable

import yaml

from .normalize import best_phone, extract_phones, instagram_handle_from_text, name_key, normalize_phone, parse_web
from .paths import CONFIG
from .schema import columns


def read_records(path: Path) -> list[dict]:
    """Apify JSON array, JSONL, or CSV (for manual url lists)."""
    text = path.read_text(encoding="utf-8-sig")
    if path.suffix == ".csv":
        return list(csv.DictReader(text.splitlines()))
    if path.suffix == ".jsonl":
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    data = json.loads(text)
    return data if isinstance(data, list) else [data]


def keyword_to_segment() -> dict[str, str]:
    q = yaml.safe_load((CONFIG / "queries.yaml").read_text(encoding="utf-8"))
    mapping = {}
    for segment, lists in q["google_maps"]["segments"].items():
        for kw in lists.get("keywords", []) + lists.get("dropped", []):
            mapping[kw.strip().lower()] = segment
    return mapping


def _blank() -> dict:
    return {c: None for c in columns("ingest")}


def _short_hash(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:12]


def google_maps(item: dict, run_id: str, segment_hint: str | None, kw_map: dict) -> dict:
    row = _blank()
    query = item.get("searchString")
    web = parse_web(item.get("website"))
    ig = web["instagram_handle"] or next(
        (instagram_handle_from_text(u) for u in item.get("instagrams") or [] if u), None)
    phone = best_phone([
        normalize_phone(item.get("phoneUnformatted") or item.get("phone")),
        (web["whatsapp_phone"], "mobile") if web["whatsapp_phone"] else (None, "none"),
    ])
    location = item.get("location") or {}
    native = item.get("placeId") or _short_hash(str(item.get("url") or item.get("title")))
    row.update(
        record_id=f"google_maps:{native}", source_id="google_maps", run_id=run_id,
        segment=kw_map.get(str(query or "").strip().lower(), segment_hint), query=query,
        evidence_url=item.get("url"), name=item.get("title"), category_raw=item.get("categoryName"),
        city=item.get("city"), address=item.get("address"), lat=location.get("lat"), lng=location.get("lng"),
        rating=item.get("totalScore"), reviews_count=item.get("reviewsCount"),
        is_closed=bool(item.get("permanentlyClosed")), google_place_id=item.get("placeId"),
        phone_e164=phone[0], phone_type=phone[1],
        website_domain=web["website_domain"], website_platform=web["website_platform"],
        store_key=web["store_key"], instagram_handle=ig,
        has_whatsapp_link=web["website_platform"] == "whatsapp",
    )
    return row


def instagram(item: dict, run_id: str, segment_hint: str | None, kw_map: dict) -> dict:
    row = _blank()
    bio = item.get("biography") or ""
    captions = " ".join((p.get("caption") or "") for p in (item.get("latestPosts") or [])[:12])
    web = parse_web(item.get("externalUrl"))
    candidates = [normalize_phone(item.get(k)) for k in ("businessPhoneNumber", "publicPhoneNumber", "contactPhoneNumber")]
    candidates += extract_phones(bio)
    if web["whatsapp_phone"]:
        candidates.append((web["whatsapp_phone"], "mobile"))
    phone = best_phone(candidates)
    handle = (item.get("username") or "").lower() or None
    row.update(
        record_id=f"instagram:{handle}", source_id="instagram", run_id=run_id, segment=segment_hint,
        query=item.get("inputUrl"), evidence_url=item.get("url") or (f"https://www.instagram.com/{handle}/" if handle else None),
        name=item.get("fullName") or handle, category_raw=item.get("businessCategoryName"),
        followers_count=item.get("followersCount"), instagram_handle=handle,
        phone_e164=phone[0], phone_type=phone[1],
        website_domain=web["website_domain"], website_platform=web["website_platform"], store_key=web["store_key"],
        has_whatsapp_link=web["website_platform"] == "whatsapp" or "wa.me/" in bio,
        text_blob=(bio + "\n" + captions).strip()[:4000] or None,
    )
    return row


def url_list(item: dict, run_id: str, segment_hint: str | None, kw_map: dict) -> dict:
    row = _blank()
    web = parse_web(item.get("url"))
    key = web["store_key"] or web["website_domain"] or web["instagram_handle"] or _short_hash(str(item.get("url")))
    row.update(
        record_id=f"salla_zid_dork:{key}", source_id="salla_zid_dork", run_id=run_id,
        segment=item.get("segment") or segment_hint, query=item.get("query"), evidence_url=item.get("url"),
        website_domain=web["website_domain"], website_platform=web["website_platform"],
        store_key=web["store_key"], instagram_handle=web["instagram_handle"],
    )
    return row


ADAPTERS: dict[str, Callable] = {"google_maps": google_maps, "instagram": instagram, "salla_zid_dork": url_list}


def ingest(source_id: str, raw_path: Path, segment_hint: str | None = None) -> list[dict]:
    adapter = ADAPTERS[source_id]
    kw_map = keyword_to_segment()
    run_id = raw_path.stem
    rows = _dedupe_exact(adapter(item, run_id, segment_hint, kw_map) for item in read_records(raw_path))
    for row in rows:
        row["name_key"] = name_key(row["name"])
    counts = Counter(r["name_key"] for r in rows if r["name_key"])
    for row in rows:
        row["name_location_count"] = counts.get(row["name_key"], 1) if row["name_key"] else None
    return rows


def _dedupe_exact(rows: Iterable[dict]) -> list[dict]:
    """Same record_id twice in one run (a place matched by two keywords): keep first, join queries."""
    by_id: dict[str, dict] = {}
    for row in rows:
        if row["record_id"] in by_id:
            kept = by_id[row["record_id"]]
            if row["query"] and row["query"] not in (kept["query"] or ""):
                kept["query"] = f"{kept['query']} | {row['query']}"
        else:
            by_id[row["record_id"]] = row
    return list(by_id.values())


def write_csv(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns("ingest"), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
