"""Stage 5, step 4.2 — BNPL fingerprint and page contacts for eligible merchants.

Target per merchant: its own website, else its Salla/Zid store page; merchants with neither are `no_site` (not checked).
Only the homepage is fetched. A page that does not load is a row with bnpl_status `fetch_failed`, never skipped.
Contacts are stored as yes/no flags only: phone values stay out of every output file.
"""
from __future__ import annotations

import csv
import re
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import httpx

from . import paths
from .bnpl import attributes, detect, markers, status_from_evidence
from .normalize import normalize_phone, parse_web, to_ascii_digits
from .rules import load_rules
from .schema import web_columns
from .web import USER_AGENT, fetch

WEB_COLUMNS = [c["name"] for c in web_columns()]
C_SAMPLE = "salla_zid_dork__C_salla_zid_d2c__sample.csv"
C_CHECK = "C_contact_check.csv"
C_CHECK_COLUMNS = ["record_id", "store_url", "platform", "icp_label", "checked_by", "http_status",
                   "phone_visible", "whatsapp_visible", "instagram_visible", "contactable", "bnpl_status", "note"]
TEMPLATE_KINDS = ("html", "icon")          # the platform-template rule covers these kinds (bnpl_markers.yaml)
CONTACT_KINDS = ("phone", "whatsapp", "instagram")

_HREF = re.compile(r"""href\s*=\s*["']([^"'<>]+)["']""", re.I)
_CONTACT_URL = re.compile(r"https?://(?:www\.)?(?:wa\.me|api\.whatsapp\.com|instagram\.com)/[^\s\"'<>\\]+", re.I)
_JSON_PHONE = re.compile(r'"(?:phone|mobile|telephone|whatsapp)\w*"\s*:\s*"([^"]{8,20})"', re.I)
_DROP = re.compile(r"<(script|style|noscript|svg)\b.*?</\1\s*>", re.I | re.S)
_TAG = re.compile(r"<[^>]+>")
_PHONE_CANDIDATE = re.compile(r"(?<![\w.])(?:\+|00)?\d[\d \-]{7,16}\d(?![\w.])")
_SAR = re.compile("ر\\.س|﷼|\u20c1|\\bSAR\\b")
_FOREIGN = re.compile(r"د\.إ|د\.ب|د\.ك|ر\.ق|ر\.ع|\b(?:AED|BHD|KWD|QAR|OMR)\b")


def read_csv(path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(path, rows: list[dict], fields: list[str]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def target(website_domain: str, store_key: str, ignore: set[str]) -> tuple[str, list[str]]:
    """(platform, urls to try in order). Own site first; hosting/directory domains are not the merchant's site."""
    d = (website_domain or "").lower()
    if d and not (d in ignore or any(d.endswith("." + x) for x in ignore)):
        return "own_site", [f"https://{d}"] + ([] if d.startswith("www.") else [f"https://www.{d}"])
    sk = (store_key or "").lower()
    if "salla.sa" in sk:
        return "salla", [f"https://{sk}"]
    if "zid.store" in sk:
        return "zid", [f"https://{sk}"]
    return "no_site", []


def visible_text(html: str) -> str:
    return re.sub(r"\s+", " ", _TAG.sub(" ", _DROP.sub(" ", html or "")))


def text_phones(text: str) -> set[tuple[str, str]]:
    """KSA numbers written with a national or international prefix (bare 9-digit runs are product ids, not phones)."""
    out = set()
    for cand in _PHONE_CANDIDATE.findall(to_ascii_digits(text)):
        digits = re.sub(r"\D", "", cand)
        if not digits.startswith(("0", "966", "92", "800")):
            continue
        number, kind = normalize_phone(digits)
        if number and kind in ("mobile", "landline", "unified", "tollfree"):
            out.add((number, kind))
    return out


def page_contacts(html: str, url: str) -> dict:
    """Contacts in links, visible text and embedded JSON (store themes often keep social links in a JSON config)."""
    html = html or ""
    unescaped = html.replace("\\/", "/")
    phones = text_phones(visible_text(html))
    for raw in _JSON_PHONE.findall(unescaped):
        number, kind = normalize_phone(raw)
        if number and kind in ("mobile", "landline", "unified", "tollfree"):
            phones.add((number, kind))
    whatsapp, instagram = set(), set()
    for v in _HREF.findall(html) + attributes(html) + _CONTACT_URL.findall(unescaped):
        low = v.strip().lower()
        if low.startswith("tel:"):
            number, kind = normalize_phone(low[4:])
            if number and kind in ("mobile", "landline", "unified", "tollfree"):
                phones.add((number, kind))
        elif "wa.me/" in low or "whatsapp.com/" in low:
            whatsapp.add(parse_web(v.strip())["whatsapp_phone"] or f"link@{url}")
        elif "instagram.com/" in low:
            handle = parse_web(v.strip())["instagram_handle"]
            if handle:
                instagram.add(handle)
    return {"phone": {p for p, _ in phones}, "mobile": {p for p, k in phones if k == "mobile"},
            "whatsapp": whatsapp, "instagram": instagram}


def analyse(urls: list[str], client: httpx.Client, use_cache: bool) -> dict:
    """Fetch the first URL that connects; return detection and contacts without keeping the HTML."""
    page = {}
    for u in urls:
        page = fetch(u, client=client, use_cache=use_cache)
        if page["status"] != 0:
            break
    out = {k: page.get(k) for k in ("final_url", "status", "ok", "error")}
    html = page.get("html") or ""
    out["evidence"] = detect(html)["evidence"] if page.get("ok") else []
    out["contacts"] = page_contacts(html, urls[0]) if page.get("ok") else {k: set() for k in (*CONTACT_KINDS, "mobile")}
    text = visible_text(html) if page.get("ok") else ""
    out["currency_sar"], out["currency_foreign"] = bool(_SAR.search(text)), bool(_FOREIGN.search(text))
    return out


def template_markers(results: dict, platform_of: dict) -> tuple[dict, list[dict]]:
    """Evidence present on >= platform_template_share of one platform's loaded pages (html/icon kinds) is a template."""
    share_min = markers()["platform_template_share"]
    dropped, table = {}, []
    for platform in ("salla", "zid"):
        ok = [u for u, p in platform_of.items() if p == platform and results[u]["ok"]]
        counts = Counter(e for u in ok for e in set(results[u]["evidence"]))
        dropped[platform] = set()
        for ev, n in counts.most_common():
            share = n / len(ok)
            is_template = share >= share_min and ev.split(":")[1] in TEMPLATE_KINDS
            if is_template:
                dropped[platform].add(ev)
            if share >= 0.5:
                table.append({"platform": platform, "pages_ok": len(ok), "evidence": ev, "share": share, "dropped": is_template})
    return dropped, table


def contact_hubs(results: dict) -> set[tuple[str, str]]:
    """(kind, value) found on more pages than rules.yaml web.contact_hub_max_pages: platform or agency contact."""
    limit = load_rules()["web"]["contact_hub_max_pages"]
    counts = Counter((k, v) for r in results.values() for k in (*CONTACT_KINDS, "mobile") for v in r["contacts"][k])
    return {kv for kv, n in counts.items() if n > limit}


def failure_reason(status, error: str) -> str:
    """Group a failed fetch: blocked for scripts (not bypassed) vs a site that is broken for everyone."""
    code = int(status or 0)
    if code in (401, 403, 429):
        return "blocked for scripts"
    if code in (404, 410):
        return "page not found"
    if code >= 500:
        return "site broken: server or TLS error"
    if (error or "").endswith(":tls"):
        return "site broken: TLS certificate"
    if (error or "").endswith(":dns"):
        return "site broken: domain does not resolve"
    return "connection error"


def yes_no(flag: bool) -> str:
    return "yes" if flag else "no"


def run(workers: int = 8, refresh: bool = False, limit: int | None = None) -> dict:
    ignore = {d.lower() for d in load_rules()["link"]["ignore_domains"]}
    merchants = [m for m in read_csv(paths.INTERIM / "merchants.csv") if not m["exclusion_reason"]]
    sample = read_csv(paths.SAMPLES / C_SAMPLE)

    rows, jobs, platform_of = [], {}, {}
    for m in merchants:
        platform, urls = target(m["website_domain"], m["store_key"], ignore)
        if urls and limit is not None and len(jobs) >= limit:
            continue
        rows.append({"merchant_id": m["merchant_id"], "segment": m["segment"], "platform": platform,
                     "target_url": urls[0] if urls else ""})
        if urls:
            jobs[urls[0]], platform_of[urls[0]] = urls, platform
    sample_targets = {s["record_id"]: target("", s["store_key"], ignore) for s in sample}
    if limit is None:
        for platform, urls in sample_targets.values():
            if urls:
                jobs.setdefault(urls[0], urls)
                platform_of[urls[0]] = platform

    with httpx.Client(follow_redirects=True, timeout=20, headers={"User-Agent": USER_AGENT}) as client, \
            ThreadPoolExecutor(max_workers=workers) as pool:
        results = dict(zip(jobs, pool.map(lambda urls: analyse(urls, client, not refresh), jobs.values())))

    dropped, template_table = template_markers(results, platform_of)
    hubs = contact_hubs(results)
    for r in results.values():
        r["contacts"] = {k: {v for v in vals if (k, v) not in hubs} for k, vals in r["contacts"].items()}

    today = date.today().isoformat()
    for row in rows:
        res = results.get(row["target_url"])
        if not res:
            row.update({c: "" for c in WEB_COLUMNS if c not in row})
            continue
        template = dropped.get(row["platform"], set())
        evidence = [e for e in res["evidence"] if e not in template]
        status, providers = status_from_evidence(evidence) if res["ok"] else ("fetch_failed", [])
        c = res["contacts"]
        checked = (lambda v: v) if res["ok"] else (lambda v: "")            # page did not load: flags are not checked
        row.update({
            "final_url": res["final_url"], "http_status": res["status"], "fetch_error": res["error"],
            "bnpl_status": status, "bnpl_providers": "|".join(providers),
            "evidence_kinds": "|".join(sorted({e.split(":")[1] for e in evidence if not e.startswith("generic_installment:")})),
            "bnpl_evidence": " ; ".join(evidence), "template_dropped": " ; ".join(e for e in res["evidence"] if e in template),
            "page_phone": checked(bool(c["phone"])), "page_mobile": checked(bool(c["mobile"])),
            "page_whatsapp": checked(bool(c["whatsapp"])), "page_instagram": checked(bool(c["instagram"])),
            "currency_sar": checked(res["currency_sar"]), "currency_foreign": checked(res["currency_foreign"]),
            "fetched_on": today,
        })
    write_csv(paths.INTERIM / "bnpl.csv", rows, WEB_COLUMNS)

    check = c_contact_check(sample, sample_targets, results, dropped) if limit is None else []
    summary = write_summary(rows, merchants, template_table, check, limit)
    return {"rows": rows, "check": check, "summary": summary}


def c_contact_check(sample: list[dict], targets: dict, results: dict, dropped: dict | None = None) -> list[dict]:
    """C contactability on the 20-store validation sample: script where the page loads, by hand where it does not.
    Rows already checked by hand (checked_by = manual_browser) are kept as they are; contactable is recomputed."""
    path = paths.SAMPLES / C_CHECK
    previous = {r["record_id"]: r for r in read_csv(path)} if path.exists() else {}
    out = []
    for s in sample:
        platform, urls = targets[s["record_id"]]
        url = urls[0] if urls else ""
        prev = previous.get(s["record_id"])
        if prev and prev["checked_by"] == "manual_browser":
            row = {**prev, "bnpl_status": prev.get("bnpl_status") or ""}
        else:
            res = results.get(url, {})
            row = {"record_id": s["record_id"], "store_url": url, "platform": platform, "icp_label": s["icp_label"],
                   "http_status": res.get("status", ""), "note": ""}
            if res.get("ok"):
                c = res["contacts"]
                evidence = [e for e in res["evidence"] if e not in (dropped or {}).get(platform, set())]
                row.update(checked_by="script", phone_visible=yes_no(c["phone"]),
                           whatsapp_visible=yes_no(c["whatsapp"]), instagram_visible=yes_no(c["instagram"]),
                           bnpl_status=status_from_evidence(evidence)[0])
            elif res.get("status") in (404, 410):
                row.update(checked_by="script", phone_visible="no", whatsapp_visible="no", instagram_visible="no",
                           bnpl_status="unclear", note="store page not found")
            else:
                row.update(checked_by="pending_manual", phone_visible="", whatsapp_visible="", instagram_visible="",
                           bnpl_status="", note="page blocked for the script: check by hand with --manual-c")
        flags = [row[k] for k in ("phone_visible", "whatsapp_visible", "instagram_visible")]
        row["contactable"] = "" if row["checked_by"] == "pending_manual" else yes_no("yes" in flags)
        out.append(row)
    write_csv(path, out, C_CHECK_COLUMNS)
    return out


MANUAL_QUESTIONS = (("phone_visible", "phone number on the page (header, footer, contact block)"),
                    ("whatsapp_visible", "WhatsApp icon or link"),
                    ("instagram_visible", "Instagram icon or link to the store's own account"))


BNPL_QUESTIONS = (("tabby", "Tabby logo or name on the page"),
                  ("other", "Tamara, MISpay, Madfu or Emkan logo or name on the page"))


def manual_bnpl_status(tabby: str, other: str) -> str:
    """Same precedence as the script; `unclear` counts against the source in the C kill criterion."""
    if tabby == "y":
        return "tabby"
    if other == "y":
        return "competitor_only"
    return "unclear" if "?" in (tabby, other) else "not_detected"


def manual_c_check(ask=input, open_url=None) -> dict:
    """Interactive check of C sample stores the script could not load: contacts and BNPL logos, only what is missing.
    Saves after every store, so it can stop and resume. y = visible, n = not visible, ? = cannot tell, q = stop."""
    import webbrowser
    open_url = open_url or webbrowser.open
    path = paths.SAMPLES / C_CHECK
    rows = read_csv(path)
    todo = [r for r in rows if r["checked_by"] == "pending_manual" or (r["checked_by"] == "manual_browser" and not r.get("bnpl_status"))]
    print(f"{len(todo)} stores to check. y = visible, n = not visible, ? = cannot tell (counts against the source), q = stop")
    for i, r in enumerate(todo, 1):
        print(f"\n[{i}/{len(todo)}] {r['store_url']}")
        open_url(r["store_url"])
        questions = (MANUAL_QUESTIONS if r["checked_by"] == "pending_manual" else ()) + BNPL_QUESTIONS
        answers = {}
        for field, question in questions:
            a = ""
            while a not in ("y", "n", "?", "q"):
                a = ask(f"   {question}? [y/n/?/q] ").strip().lower()
            if a == "q":
                break
            answers[field] = a
        if len(answers) < len(questions):
            print("stopped; this store stays as it was")
            break
        if r["checked_by"] == "pending_manual":
            r.update({f: {"y": "yes", "n": "no", "?": "unclear"}[answers[f]] for f, _ in MANUAL_QUESTIONS})
            r["contactable"] = yes_no("yes" in [r[f] for f, _ in MANUAL_QUESTIONS])
            r["checked_by"] = "manual_browser"
        r["bnpl_status"] = manual_bnpl_status(answers["tabby"], answers["other"])
        r["note"] = f"checked by hand in a browser {date.today().isoformat()}"
        write_csv(path, rows, C_CHECK_COLUMNS)
    done = [r for r in rows if r["checked_by"] != "pending_manual"]
    result = {"total": len(rows), "checked": len(done), "contactable": sum(r["contactable"] == "yes" for r in done),
              "bnpl_checked": sum(bool(r.get("bnpl_status")) for r in rows)}
    print(f"\nchecked {result['checked']}/{result['total']}, contactable {result['contactable']}, "
          f"BNPL checked {result['bnpl_checked']}/{result['total']}")
    return result


def _table(header: list[str], rows: list[list]) -> list[str]:
    return ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)] + ["| " + " | ".join(map(str, r)) + " |" for r in rows]


def write_summary(rows: list[dict], merchants: list[dict], template_table: list[dict], check: list[dict], limit) -> str:
    segs = sorted({r["segment"] for r in rows})
    statuses = ["tabby", "competitor_only", "generic_installment", "not_detected", "fetch_failed"]
    lines = ["# BNPL fingerprint and page contacts (stage 5, step 4.2)", "",
             f"Run {date.today().isoformat()}{f' — LIMITED to {limit} pages, not a result' if limit is not None else ''}. "
             "Homepage only: `not_detected` does not mean no BNPL. Markers: `config/bnpl_markers.yaml`. "
             "Eligible merchants only (`data/interim/merchants.csv`, exclusion_reason empty).", "",
             "## Targets", ""]
    lines += _table(["segment", "eligible", "own_site", "salla", "zid", "no_site", "page loaded", "fetch_failed"],
                    [[s, sum(r["segment"] == s for r in rows),
                      *[sum(r["segment"] == s and r["platform"] == p for r in rows) for p in ("own_site", "salla", "zid", "no_site")],
                      sum(r["segment"] == s and r["bnpl_status"] not in ("", "fetch_failed") for r in rows),
                      sum(r["segment"] == s and r["bnpl_status"] == "fetch_failed" for r in rows)] for s in segs])
    lines += ["", "## BNPL status (merchants with a site or store)", ""]
    lines += _table(["segment", *statuses], [[s, *[sum(r["segment"] == s and r["bnpl_status"] == st for r in rows) for st in statuses]] for s in segs])
    lines += ["", "## Evidence kind behind provider detections", "",
              "A merchant counts once per provider and kind (it can have several kinds). `icon` is not verified.", ""]
    kind_counts = Counter(
        (r["segment"], provider, kind)
        for r in rows
        for provider, kind in {tuple(ev.split(":", 2)[:2]) for ev in filter(None, r.get("bnpl_evidence", "").split(" ; "))}
        if provider != "generic_installment")
    lines += _table(["segment", "provider", "kind", "merchants"], [[*k, n] for k, n in sorted(kind_counts.items())]) if kind_counts else ["none"]
    only_icon = Counter(r["segment"] for r in rows if r.get("bnpl_status") == "tabby"
                        and {e.split(":")[1] for e in r["bnpl_evidence"].split(" ; ") if e.startswith("tabby:")} == {"icon"})
    lines += ["", f"`tabby` detected by icon only (unverified kind): {dict(only_icon) or 'none'}", "",
              "## Platform templates", "",
              "Evidence on at least half of one platform's loaded pages; `dropped` = html/icon on >= "
              f"{markers()['platform_template_share']:.0%} (rule fixed before this run).", ""]
    lines += _table(["platform", "pages loaded", "evidence", "share", "dropped"],
                    [[t["platform"], t["pages_ok"], f"`{t['evidence'][:90]}`", f"{t['share']:.2f}", t["dropped"]] for t in template_table]) \
        if template_table else ["none"]
    lines += ["", "## Fetch failures", ""]
    fails = Counter((r["segment"], r["platform"], failure_reason(r["http_status"], r["fetch_error"]),
                     f"HTTP {r['http_status']}" if str(r["http_status"]) != "0" else r["fetch_error"])
                    for r in rows if r.get("bnpl_status") == "fetch_failed")
    lines += ["Blocked pages are not bypassed (methodology). Broken sites fail for any visitor, not only for the script.", ""]
    lines += _table(["segment", "platform", "reason", "detail", "merchants"], [[*k, n] for k, n in sorted(fails.items())]) if fails else ["none"]
    lines += ["", "## Page contacts (merchants whose page loaded)", "",
              f"Contact values on more than {load_rules()['web']['contact_hub_max_pages']} pages are ignored (platform or agency). "
              "Flags only, no values stored.", ""]
    loaded = [r for r in rows if r.get("bnpl_status") not in ("", "fetch_failed")]
    lines += _table(["segment", "loaded", "phone", "mobile", "whatsapp", "instagram", "SAR price", "foreign currency"],
                    [[s, sum(r["segment"] == s for r in loaded),
                      *[sum(r["segment"] == s and r[k] is True for r in loaded)
                        for k in ("page_phone", "page_mobile", "page_whatsapp", "page_instagram", "currency_sar", "currency_foreign")]]
                     for s in segs])
    if check:
        by = Counter(r["checked_by"] for r in check)
        done = [r for r in check if r["checked_by"] != "pending_manual"]
        yes = sum(r["contactable"] == "yes" for r in done)
        lines += ["", "## Segment C contactability — validation sample (`data/samples/C_contact_check.csv`)", "",
                  "Definition (methodology 2026-09-17): phone, WhatsApp or tel link, or Instagram visible on the store homepage. "
                  "Threshold 0.50, fixed before data. The script reads links, text and embedded JSON of the homepage; a contact "
                  "that appears only after JavaScript runs can be missed, which biases the script rows towards `no`.", ""]
        lines += _table(["checked_by", "stores", "contactable"],
                        [[k, n, "—" if k == "pending_manual" else sum(r["contactable"] == "yes" for r in check if r["checked_by"] == k)]
                         for k, n in sorted(by.items())])
        if by.get("pending_manual"):
            lines += ["", f"**Verdict pending:** {by['pending_manual']} of {len(check)} stores still to check by hand "
                          f"(so far {yes}/{len(done)} contactable)."]
        else:
            rate = yes / len(check)
            lines += ["", f"**contactable_rate {rate:.2f}** ({yes}/{len(check)}) -> recommend: "
                          f"{'accept' if rate >= 0.5 else 'reject'} (threshold 0.50)."]
        bnpl = Counter(r.get("bnpl_status") or "pending" for r in check)
        lines += ["", "### Segment C kill criterion: stores already showing a BNPL provider", "",
                  "`config/icp.yaml`: reject C if > 0.60 of stores already show a BNPL provider. Measured on the same 20-store "
                  "sample (Salla blocks scripts): script where the page loads, by hand where it does not. Homepage only; "
                  "`unclear` counts against the source.", ""]
        lines += _table(["bnpl_status", "stores"], [[k, n] for k, n in sorted(bnpl.items())])
        if bnpl.get("pending"):
            lines += ["", f"**Kill criterion pending:** {bnpl['pending']} stores without a BNPL check."]
        else:
            share = (bnpl["tabby"] + bnpl["competitor_only"] + bnpl["unclear"]) / len(check)
            lines += ["", f"**share with a provider (unclear counted as yes) {share:.2f}** -> "
                          f"{'kill criterion hit: reject C' if share > 0.60 else 'kill criterion not hit'} (threshold 0.60)."]
    text = "\n".join(lines) + "\n"
    (paths.SAMPLES / "bnpl_summary.md").write_text(text, encoding="utf-8")
    return text
