"""Step 4.3 — LLM enrichment of eligible A and B merchants: owner name, ticket, Arabic opener (all `_inferred`).

Input per merchant: business name, Maps categories and, when the homepage loaded in step 4.2, its visible text (read from
data/cache/web/, never fetched again; phone numbers masked before sending). Answers are cached per merchant and prompt
version in data/cache/llm/, so a re-run costs nothing. Owner names and hooks stay in data/interim/ (not committed).
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import random
import re
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from functools import lru_cache

import httpx
import yaml

from . import paths
from .fingerprint import QA_TABBY, final_tabby, read_csv, visible_text, write_csv
from .schema import enrich_columns

ENRICH_COLUMNS = [c["name"] for c in enrich_columns()]
_PHONE_RUN = re.compile(r"\+?\d[\d \-]{6,}\d")
_TASHKEEL = re.compile(r"[\u064B-\u0652\u0670\u0640]")
_AR_MAP = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ة": "ه", "ى": "ي", "ؤ": "و", "ئ": "ي"})

ANSWER_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["owner_name_inferred", "owner_role_inferred", "owner_evidence_inferred", "ticket_sar_min_inferred",
                 "ticket_sar_max_inferred", "ticket_basis_inferred", "hook_ar_inferred", "hook_fact_inferred"],
    "properties": {
        "owner_name_inferred": {"type": ["string", "null"]},
        "owner_role_inferred": {"type": "string", "enum": ["owner", "founder", "medical_director",
                                                           "doctor_or_person_in_business_name", "manager", "unknown"]},
        "owner_evidence_inferred": {"type": "string"},
        "ticket_sar_min_inferred": {"type": ["integer", "null"]},
        "ticket_sar_max_inferred": {"type": ["integer", "null"]},
        "ticket_basis_inferred": {"type": "string", "enum": ["prices_on_page", "category_typical", "unknown"]},
        "hook_ar_inferred": {"type": "string"},
        "hook_fact_inferred": {"type": "string"},
    },
}


@lru_cache
def config() -> dict:
    return yaml.safe_load((paths.CONFIG / "llm.yaml").read_text(encoding="utf-8"))


def api_key() -> str:
    """OPENAI_API_KEY from the environment or the project's .env (never printed, never written anywhere)."""
    if os.environ.get("OPENAI_API_KEY"):
        return os.environ["OPENAI_API_KEY"]
    env = paths.ROOT / ".env"
    for line in env.read_text(encoding="utf-8").splitlines() if env.exists() else []:
        if line.startswith("OPENAI_API_KEY="):
            return line.split("=", 1)[1].strip()
    raise SystemExit("OPENAI_API_KEY is missing: put it in .env (see .env.example)")


def cached_html(url: str) -> str:
    """Homepage HTML from the step 4.2 cache only; own sites were also tried with www."""
    if not url:
        return ""
    candidates = [url]
    if url.startswith("https://") and not url.startswith("https://www."):
        candidates.append("https://www." + url[len("https://"):])
    for u in candidates:
        key = hashlib.sha1(u.encode("utf-8")).hexdigest()
        meta, html = paths.DATA / "cache" / "web" / f"{key}.json", paths.DATA / "cache" / "web" / f"{key}.html"
        if meta.exists() and json.loads(meta.read_text(encoding="utf-8")).get("ok") and html.exists():
            return html.read_text(encoding="utf-8")
    return ""


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", _TASHKEEL.sub("", text or "").translate(_AR_MAP)).strip().casefold()


def candidates() -> list[dict]:
    """Eligible A and B merchants, minus Tabby merchants, with the text each one will be sent.
    A `tabby` detection is skipped unless the QA file marks it a false positive."""
    cfg = config()
    web = {r["merchant_id"]: r for r in read_csv(paths.INTERIM / "bnpl.csv")}
    qa_path = paths.SAMPLES / QA_TABBY
    qa = {r["merchant_id"]: r for r in read_csv(qa_path)} if qa_path.exists() else {}
    out = []
    for m in read_csv(paths.INTERIM / "merchants.csv"):
        if m["exclusion_reason"] or m["segment"] not in cfg["segments"]:
            continue
        w = web.get(m["merchant_id"], {})
        if w.get("bnpl_status") == "tabby" and (m["merchant_id"] not in qa or final_tabby(qa[m["merchant_id"]])):
            continue
        loaded = w.get("bnpl_status") not in ("", "fetch_failed", None)
        page = visible_text(cached_html(w.get("target_url", ""))) if loaded else ""
        page = _PHONE_RUN.sub("[phone]", page)[: cfg["max_input_chars"]]
        out.append({"merchant_id": m["merchant_id"], "segment": m["segment"], "name": m["name"],
                    "categories": m["categories"], "cities": m["cities"], "page_text": page})
    return sorted(out, key=lambda c: c["merchant_id"])


def user_message(c: dict) -> str:
    return (f"Business name: {c['name']}\nGoogle Maps categories: {c['categories'] or 'n/a'}\n"
            f"Kind of business: {config()['segment_description'][c['segment']]}\nCity: {c['cities'] or 'n/a'}\n"
            f"Homepage text (phone numbers masked, may be cut):\n\"\"\"\n{c['page_text'] or '(no website text available)'}\n\"\"\"")


def cache_path(c: dict):
    key = hashlib.sha1(f"{config()['prompt_version']}|{config()['model']}|{c['merchant_id']}|{user_message(c)}".encode("utf-8")).hexdigest()
    d = paths.DATA / "cache" / "llm"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{key}.json"


def call(c: dict, client: httpx.Client) -> dict:
    """One structured-output request, cached. Returns {answer, input_tokens, output_tokens, cost_usd, error, cached}."""
    path = cache_path(c)
    if path.exists():
        return {**json.loads(path.read_text(encoding="utf-8")), "cached": True}
    cfg = config()
    body = {"model": cfg["model"], "max_completion_tokens": cfg["max_output_tokens"],
            "messages": [{"role": "system", "content": cfg["system_prompt"]}, {"role": "user", "content": user_message(c)}],
            "response_format": {"type": "json_schema", "json_schema": {"name": "merchant_facts", "strict": True, "schema": ANSWER_SCHEMA}}}
    if cfg.get("reasoning_effort"):
        body["reasoning_effort"] = cfg["reasoning_effort"]
    out = {"answer": None, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0, "error": ""}
    for attempt in range(4):
        try:
            r = client.post(cfg["endpoint"], json=body)
        except httpx.HTTPError as e:
            out["error"] = type(e).__name__
            time.sleep(2 ** attempt)
            continue
        if r.status_code in (429, 500, 502, 503) and attempt < 3:
            time.sleep(2 ** attempt * 2)
            continue
        data = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        if r.status_code != 200:
            out["error"] = f"HTTP {r.status_code}: {(data.get('error') or {}).get('message', '')[:200]}"
            return out                                   # errors are not cached: a re-run retries them
        usage = data.get("usage") or {}
        price = cfg["price_usd_per_1m_tokens"]
        out["input_tokens"], out["output_tokens"] = usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)
        out["cost_usd"] = out["input_tokens"] / 1e6 * price["input"] + out["output_tokens"] / 1e6 * price["output"]
        choice = (data.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        if message.get("refusal") or choice.get("finish_reason") != "stop":
            out["error"] = f"no answer: finish_reason={choice.get('finish_reason')} refusal={bool(message.get('refusal'))}"
        else:
            out["answer"] = json.loads(message["content"])
            path.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
        return out
    return out


def row(c: dict, res: dict) -> dict:
    a = res.get("answer") or {}
    name = a.get("owner_name_inferred") or ""
    source = norm(f"{c['name']} {c['page_text']}")
    return {"merchant_id": c["merchant_id"], "segment": c["segment"],
            "input_kind": "page_text" if c["page_text"] else "name_only", "input_chars": len(c["page_text"]),
            **{k: ("" if a.get(k) is None else a.get(k)) for k in ANSWER_SCHEMA["required"]},
            "owner_name_in_source": bool(name) and norm(name) in source,
            "model": config()["model"], "prompt_version": config()["prompt_version"],
            "input_tokens": res["input_tokens"], "output_tokens": res["output_tokens"],
            "cost_usd": round(res["cost_usd"], 6), "cached": res.get("cached", False), "error": res["error"],
            "enriched_on": date.today().isoformat()}


def pick(pool: list[dict], sample: int, seed: int) -> list[dict]:
    """Trial sample stratified by input kind: half with homepage text, the rest name only."""
    rng = random.Random(seed)
    with_text, name_only = [c for c in pool if c["page_text"]], [c for c in pool if not c["page_text"]]
    chosen = rng.sample(with_text, min(sample // 2, len(with_text)))
    return chosen + rng.sample(name_only, min(sample - len(chosen), len(name_only)))


def run(sample: int | None = None, workers: int = 4, dry_run: bool = False, transport=None) -> dict:
    cfg = config()
    pool = candidates()
    chosen = pick(pool, sample, cfg["trial"]["seed"]) if sample else pool
    if dry_run:
        return summary(pool, chosen, [], dry_run=True)
    headers = {"Authorization": f"Bearer {api_key()}", "Content-Type": "application/json"}
    rows, spent = [], 0.0
    with httpx.Client(timeout=120, headers=headers, transport=transport) as client, ThreadPoolExecutor(max_workers=workers) as ex:
        for start in range(0, len(chosen), workers):
            if spent >= cfg["budget_usd"]:
                print(f"budget stop: spent ${spent:.4f} >= ${cfg['budget_usd']}")
                break
            batch = chosen[start:start + workers]
            for c, res in zip(batch, ex.map(lambda c: call(c, client), batch)):
                spent += 0 if res.get("cached") else res["cost_usd"]
                rows.append(row(c, res))
    write_csv(paths.INTERIM / ("enrich_trial.csv" if sample else "enrich.csv"), rows, ENRICH_COLUMNS)
    out = summary(pool, chosen, rows)
    write_summary_md(out, trial=bool(sample))
    return out


def check_model(transport=None) -> str:
    """Free call: does the configured model exist for this key?"""
    cfg = config()
    with httpx.Client(timeout=30, headers={"Authorization": f"Bearer {api_key()}"}, transport=transport) as client:
        r = client.get(f"https://api.openai.com/v1/models/{cfg['model']}")
    if r.status_code == 200:
        return f"model {cfg['model']}: available"
    message = (r.json().get("error") or {}).get("message", "") if r.headers.get("content-type", "").startswith("application/json") else ""
    return f"model {cfg['model']}: HTTP {r.status_code} {message[:200]}"


def review_lines(rows: list[dict]) -> list[str]:
    """Trial review without personal data: owner names are replaced by [owner] everywhere."""
    lines = []
    for r in rows:
        hook = r["hook_ar_inferred"]
        if r["owner_name_inferred"]:
            hook = hook.replace(r["owner_name_inferred"], "[owner]")
            for part in r["owner_name_inferred"].split():                   # also partial forms of the name
                if len(part) >= 3 and not part.endswith("."):
                    hook = hook.replace(part, "[owner]")
        hook = _PHONE_RUN.sub("[phone]", hook)
        ticket = f"{r['ticket_sar_min_inferred'] or '?'}-{r['ticket_sar_max_inferred'] or '?'} SAR ({r['ticket_basis_inferred']})"
        lines.append(f"- {r['merchant_id']} {r['segment'][:1]} {r['input_kind']} {r['input_chars']} chars | owner: "
                     f"{'yes' if r['owner_name_inferred'] else 'no'} role={r['owner_role_inferred']} in_source={r['owner_name_in_source']} "
                     f"| ticket {ticket} | {r['output_tokens']} out tok | {r['error'] or 'ok'}\n"
                     f"    fact: {r['hook_fact_inferred']}\n    hook: {hook}")
    return lines


def write_summary_md(out: dict, trial: bool) -> None:
    lines = [f"# LLM enrichment (step 4.3){' — TRIAL' if trial else ''}", "",
             f"Model `{config()['model']}`, prompt `{config()['prompt_version']}`, run {date.today().isoformat()}. "
             "Counts only: names and hooks stay in data/interim/. All model fields end with `_inferred`; "
             "Arabic hooks are AI-drafted and not native-reviewed.", ""]
    for k, v in out.items():
        lines.append(f"- {k}: {v}")
    name = "enrich_trial_summary.md" if trial else "enrich_summary.md"
    (paths.SAMPLES / name).write_text("\n".join(lines) + "\n", encoding="utf-8")


def gate_g3(done: list[dict]) -> dict:
    """Gate G3 inputs per segment, with the usage rules of config/llm.yaml applied (verified name, page-based hook,
    price seen on the page). contactable = mobile, Instagram or WhatsApp link from Google Maps (merchants.csv)."""
    merchants = {m["merchant_id"]: m for m in read_csv(paths.INTERIM / "merchants.csv")}
    stats = {}
    for seg in sorted({r["segment"] for r in done}):
        rs = [r for r in done if r["segment"] == seg]
        contact = [merchants.get(r["merchant_id"], {}).get("contactable") == "True" for r in rs]
        named = [str(r["owner_name_in_source"]) == "True" for r in rs]
        stats[seg] = {"merchants": len(rs), "contactable": sum(contact), "owner_name_verified": sum(named),
                      "name_and_contactable": sum(a and b for a, b in zip(named, contact)),
                      "hook_from_page": sum(r["input_kind"] == "page_text" for r in rs),
                      "price_on_page": sum(r["ticket_basis_inferred"] == "prices_on_page" for r in rs)}
    return stats


def summary(pool: list[dict], chosen: list[dict], rows: list[dict], dry_run: bool = False) -> dict:
    cfg = config()
    price = cfg["price_usd_per_1m_tokens"]
    kinds = Counter(("page_text" if c["page_text"] else "name_only") for c in pool)
    est_in = sum(len(user_message(c)) + len(cfg["system_prompt"]) for c in chosen) / 2.5     # rough chars per token
    out = {"pool": len(pool), "pool_by_segment": dict(Counter(c["segment"] for c in pool)), "pool_by_input": dict(kinds),
           "chosen": len(chosen), "estimated_input_tokens": int(est_in)}
    if dry_run:
        out["estimated_cost_input_only_usd"] = round(est_in / 1e6 * price["input"], 4)
        return out
    done = [r for r in rows if not r["error"]]
    new = [r for r in rows if not r["cached"]]
    cost = sum(r["cost_usd"] for r in new)
    per_call = sum(r["cost_usd"] for r in done) / len(done) if done else 0.0
    projected = 0.0                                     # weighted by input kind, because the trial is stratified
    for kind, n in kinds.items():
        costs = [r["cost_usd"] for r in done if r["input_kind"] == kind]
        projected += (sum(costs) / len(costs) if costs else per_call) * n
    out.update({
        "answered": len(done), "errors": Counter(r["error"][:60] for r in rows if r["error"]),
        "input_tokens": sum(r["input_tokens"] for r in rows), "output_tokens": sum(r["output_tokens"] for r in rows),
        "cost_this_run_usd": round(cost, 4), "cost_all_answers_usd": round(sum(r["cost_usd"] for r in done), 4),
        "cost_per_merchant_usd": round(per_call, 5),
        "cost_per_merchant_by_input_usd": {k: round(sum(r["cost_usd"] for r in done if r["input_kind"] == k) /
                                                     max(1, sum(r["input_kind"] == k for r in done)), 5) for k in kinds},
        "projected_all_usd": round(projected, 3),
        "owner_name_given": sum(bool(r["owner_name_inferred"]) for r in done),
        "owner_name_in_source": sum(r["owner_name_in_source"] for r in done),
        "owner_roles": dict(Counter(r["owner_role_inferred"] for r in done)),
        "ticket_basis": dict(Counter(r["ticket_basis_inferred"] for r in done)),
        "by_input": dict(Counter((r["input_kind"], bool(r["owner_name_in_source"])) for r in done)),
        "g3_by_segment": gate_g3(done),
    })
    return out
