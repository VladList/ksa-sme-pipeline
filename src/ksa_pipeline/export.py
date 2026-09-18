"""Phase 5, step 5.3 — export the scored list.

Masked export (committed): output/public/scored_masked.csv, top50_masked.csv and ksa_sme_pipeline.xlsx
(sheets README, Sources, Scored, Top-50, Reserve). Phone numbers are masked and every value is checked for
an unmasked KSA mobile before anything is written.
Private export (never committed): data/private/top50_contacts.csv with the real numbers, built on demand.
"""
from __future__ import annotations

import csv
from datetime import date

import yaml

from . import paths, pii
from .fingerprint import read_csv, write_csv
from .schema import export_columns

TOP_COLUMNS = [c["name"] for c in export_columns()]                 # contract: config/schema.yaml
MASKED_COLUMNS = [c for c in TOP_COLUMNS if c != "hook_ar_ai_drafted"]   # the opener is in the Top-50 file only
PRIVATE_COLUMNS = ["top_rank", "merchant_id", "segment", "cities", "name", "score", "phone_e164", "phone_type", "contact_note",
                   "instagram_handle", "website_domain", "owner_name_inferred", "owner_name_verified", "hook_ar_ai_drafted"]


def sources() -> list[dict]:
    data = yaml.safe_load((paths.DATA / "sources.yaml").read_text(encoding="utf-8"))
    out = []
    for s in data["sources"]:
        out.append({"id": s.get("id", ""), "role": s.get("role", ""), "status": s.get("status", ""),
                    "decided_on": str(s.get("decided_on", "")), "segments": ", ".join(s.get("segments", {}) or {}),
                    "note": " ".join(str(s.get("note", "") or s.get("rejection_reason", "")).split())[:500]})
    return out


def contact_note(m: dict, web: dict) -> str:
    """Where the channel actually is, because a merchant can be reachable without a number in Google Maps."""
    if m.get("phone_type") == "mobile":
        return "mobile in Google Maps"
    if m.get("contactable") == "True" and not m.get("instagram_handle"):
        return "WhatsApp link in Google Maps"
    if web.get("page_mobile") == "True" or web.get("page_whatsapp") == "True":
        return "number on the merchant website (not stored)"
    if m.get("instagram_handle"):
        return "Instagram"
    return f"{m.get('phone_type', '')} in Google Maps".strip() if m.get("phone_e164") else ""


def rows() -> tuple[list[dict], list[dict]]:
    """(masked rows for every merchant, private rows for the Top-50)."""
    merchants = {m["merchant_id"]: m for m in read_csv(paths.INTERIM / "merchants.csv")}
    web = {r["merchant_id"]: r for r in read_csv(paths.INTERIM / "bnpl.csv")}
    enrich_path = paths.INTERIM / "enrich.csv"
    enrich = {r["merchant_id"]: r for r in read_csv(enrich_path)} if enrich_path.exists() else {}
    masked, private = [], []
    for s in read_csv(paths.INTERIM / "scored.csv"):
        m, e = merchants.get(s["merchant_id"], {}), enrich.get(s["merchant_id"], {})
        hook = e.get("hook_ar_inferred", "") if e.get("input_kind") == "page_text" else ""
        row = {k: s.get(k, "") for k in MASKED_COLUMNS if k in s}
        row.update({"phone_masked": pii.mask_mobile(m.get("phone_e164", "")), "instagram_handle": m.get("instagram_handle", ""),
                    "website_domain": m.get("website_domain", ""), "contact_note": contact_note(m, web.get(s["merchant_id"], {}))})
        masked.append(row)
        if s.get("top_rank"):
            private.append({"top_rank": int(s["top_rank"]), "merchant_id": s["merchant_id"], "segment": s["segment"],
                            "cities": s["cities"], "name": s["name"], "score": s["score"], "phone_e164": m.get("phone_e164", ""),
                            "phone_type": m.get("phone_type", ""), "contact_note": contact_note(m, web.get(s["merchant_id"], {})),
                            "instagram_handle": m.get("instagram_handle", ""),
                            "website_domain": m.get("website_domain", ""), "owner_name_inferred": e.get("owner_name_inferred", ""),
                            "owner_name_verified": e.get("owner_name_in_source", ""), "hook_ar_ai_drafted": hook})
        if s.get("top_rank"):
            masked[-1]["hook_ar_ai_drafted"] = hook
    masked.sort(key=lambda r: (r["top_rank"] and int(r["top_rank"]) or 999, r["merchant_id"]))
    private.sort(key=lambda r: r["top_rank"])
    return masked, private


def check_masked(rows_list: list[dict]) -> None:
    """Fail before writing if any value still carries an unmasked KSA mobile number."""
    leaks = [f"{r.get('merchant_id')}:{k}" for r in rows_list for k, v in r.items() if isinstance(v, str) and pii.find_mobiles(v)]
    assert not leaks, f"unmasked mobile numbers in the export: {leaks[:5]}"


def readme_lines(masked: list[dict]) -> list[list[str]]:
    scored = [r for r in masked if not r["score_exclusion"]]
    top = [r for r in masked if r["top_rank"]]
    def n(pred, source=scored):
        return sum(1 for r in source if pred(r))
    return [["KSA SME merchant pipeline — scored lead list", ""],
            ["Exported", date.today().isoformat()],
            ["Repository", "github.com/VladList/ksa-sme-pipeline (method, configs, source validation, observations)"],
            ["", ""],
            ["Funnel", ""],
            ["merchants after entity resolution", str(len(masked))],
            ["scored (eligible A and B, not already on Tabby)", str(len(scored))],
            ["A-tier with a direct channel", str(n(lambda r: r["tier"] == "A"))],
            ["Top-50", str(len(top))],
            ["reserve (tied with the last Top-50 member)", str(n(lambda r: "reserve:" in r["flags"]))],
            ["", ""],
            ["How to read", ""],
            ["score", "0-100, config/scoring.yaml v1, fixed before the first calculation"],
            ["tier", "A >= 82.5, B >= 65, C below"],
            ["channel", "mobile_or_whatsapp(_and_name) | instagram | other_phone | none"],
            ["bnpl_status_final", "not_detected | competitor_only | generic_installment | unchecked (no site or page blocked)"],
            ["hook_ar_ai_drafted", "Arabic opener written by an LLM from the merchant's homepage: a draft, not native-reviewed"],
            ["phone_masked", "numbers are masked; scripts/08_export.py --private writes the real ones to data/private/"],
            ["contact_note", "where the channel is: a lead can carry a mobile only on its website, which the pipeline does not store"],
            ["", ""],
            ["Limitations", ""],
            ["ticket", "not measured: prices appear on 12 of 519 homepages; Ticket fit uses the segment range"],
            ["decision maker", "name verified for 48 of 519 candidates, mostly from the clinic name — not a confirmed owner"],
            ["BNPL coverage", "homepage only; 384 of 519 candidates have no website or a page blocked for scripts"],
            ["medical categories", f"{n(lambda r: 'medical' in r['flags'], top)} of the Top-50 need a Risk decision"],
            ["segment B", "Jeddah relevance 0.40 in validation; most B merchants have no website, so the Top-50 tests B weakly"],
            ["segment C", "rejected: 14 of 20 sampled Salla/Zid stores already show a BNPL provider"]]


def workbook(masked: list[dict], path) -> None:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    head_font, head_fill = Font(name="Arial", size=10, bold=True, color="FFFFFF"), PatternFill("solid", fgColor="1F4E79")
    body_font = Font(name="Arial", size=10)

    def sheet(title: str, columns: list[str], data: list[dict], freeze: bool = True):
        ws = wb.create_sheet(title)
        ws.append(columns)
        for r in data:
            ws.append([r.get(c, "") for c in columns])
        for cell in ws[1]:
            cell.font, cell.fill, cell.alignment = head_font, head_fill, Alignment(vertical="center")
        for row in ws.iter_rows(min_row=2):
            for cell in row:
                cell.font = body_font
        for i, c in enumerate(columns, 1):
            width = max(len(c), *(len(str(r.get(c, ""))) for r in data)) if data else len(c)
            ws.column_dimensions[get_column_letter(i)].width = min(max(width + 2, 10), 48)
        if freeze:
            ws.freeze_panes, ws.auto_filter.ref = "A2", ws.dimensions
        return ws

    ws = wb.active
    ws.title = "README"
    for line in readme_lines(masked):
        ws.append(line)
    for row in ws.iter_rows():
        for cell in row:
            cell.font = Font(name="Arial", size=10, bold=cell.column == 1 and not str(cell.value or "").startswith(" "))
    ws.column_dimensions["A"].width, ws.column_dimensions["B"].width = 46, 100

    top = [r for r in masked if r["top_rank"]]
    sheet("Top-50", TOP_COLUMNS, top)
    sheet("Reserve", MASKED_COLUMNS, [r for r in masked if "reserve:" in r["flags"]])
    sheet("Scored", MASKED_COLUMNS, masked)
    sheet("Sources", ["id", "role", "status", "decided_on", "segments", "note"], sources())
    wb.save(path)


def run(private: bool = False) -> dict:
    masked, priv = rows()
    check_masked(masked)
    out = paths.ROOT / "output" / "public"
    out.mkdir(parents=True, exist_ok=True)
    write_csv(out / "scored_masked.csv", [{k: r.get(k, "") for k in MASKED_COLUMNS} for r in masked], MASKED_COLUMNS)
    write_csv(out / "top50_masked.csv", [{k: r.get(k, "") for k in TOP_COLUMNS} for r in masked if r["top_rank"]], TOP_COLUMNS)
    workbook(masked, out / "ksa_sme_pipeline.xlsx")
    result = {"merchants": len(masked), "top": sum(1 for r in masked if r["top_rank"]),
              "files": ["output/public/scored_masked.csv", "output/public/top50_masked.csv", "output/public/ksa_sme_pipeline.xlsx"]}
    if private:
        d = paths.DATA / "private"
        d.mkdir(parents=True, exist_ok=True)
        write_csv(d / "top50_contacts.csv", priv, PRIVATE_COLUMNS)
        result["files"].append("data/private/top50_contacts.csv (not committed)")
    return result
