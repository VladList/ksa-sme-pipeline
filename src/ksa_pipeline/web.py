"""Polite page fetching with an on-disk cache (data/cache/web/, not committed: pages contain contact data)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import httpx

from . import paths

USER_AGENT = "Mozilla/5.0 (compatible; ksa-sme-pipeline/0.1; merchant research for a portfolio project)"


def cache_dir() -> Path:
    d = paths.DATA / "cache" / "web"
    d.mkdir(parents=True, exist_ok=True)
    return d


def transient(status: int) -> bool:
    """Network errors, rate limits and 5xx are not cached, so a rerun retries them (403/404 are stable answers)."""
    return status == 0 or status == 429 or status >= 500


def error_label(e: Exception) -> str:
    """Exception type plus the cause a reader needs: an expired certificate or a dead domain is a broken site."""
    detail = str(e).lower()
    if "certificate" in detail or "ssl" in detail:
        return f"{type(e).__name__}:tls"
    if any(s in detail for s in ("nodename nor servname", "name or service not known", "name resolution", "getaddrinfo")):
        return f"{type(e).__name__}:dns"
    return type(e).__name__


def fetch(url: str, client: httpx.Client | None = None, use_cache: bool = True) -> dict:
    """Return {url, final_url, status, ok, html, error}. Failures are data, not exceptions."""
    key = hashlib.sha1(url.encode("utf-8")).hexdigest()
    html_path, meta_path = cache_dir() / f"{key}.html", cache_dir() / f"{key}.json"
    if use_cache and meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        meta["html"] = html_path.read_text(encoding="utf-8") if html_path.exists() else ""
        return meta
    own = client is None
    client = client or httpx.Client(follow_redirects=True, timeout=20, headers={"User-Agent": USER_AGENT})
    try:
        r = client.get(url)
        meta = {"url": url, "final_url": str(r.url), "status": r.status_code, "ok": r.status_code < 400, "error": ""}
        html = r.text if meta["ok"] else ""
    except httpx.HTTPError as e:
        meta = {"url": url, "final_url": "", "status": 0, "ok": False, "error": error_label(e)}
        html = ""
    finally:
        if own:
            client.close()
    if not transient(meta["status"]):
        meta_path.write_text(json.dumps(meta), encoding="utf-8")
        html_path.write_text(html, encoding="utf-8")
    return {**meta, "html": html}
