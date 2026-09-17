import csv

from ksa_pipeline import fingerprint, paths
from ksa_pipeline.resolve import MERCHANT_COLUMNS

ZID_ICON = '<img src="https://media.zid.store/static/tabby2.svg"><a href="https://instagram.com/zid.sa">zid</a>'


def merchant(i, segment, **kw):
    m = {c: "" for c in MERCHANT_COLUMNS}
    m.update(merchant_id=f"m_{i}", segment=segment, **kw)
    return m


def page(url, status=200, html=""):
    return {"url": url, "final_url": url, "status": status, "ok": 0 < status < 400, "error": "" if status else "ConnectError",
            "html": html}


def write(path, rows, fields):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def setup(tmp_path, monkeypatch, pages):
    (tmp_path / "interim").mkdir()
    (tmp_path / "samples").mkdir()
    monkeypatch.setattr(paths, "INTERIM", tmp_path / "interim")
    monkeypatch.setattr(paths, "SAMPLES", tmp_path / "samples")
    monkeypatch.setattr(fingerprint, "fetch", lambda url, client=None, use_cache=True: pages.get(url, page(url, 0)))
    zid = [merchant(10 + i, "C_salla_zid_d2c", store_key=f"s{i}.zid.store") for i in range(5)]
    merchants = [
        merchant(1, "A_aesthetic_clinics", website_domain="clinic.sa"),
        merchant(2, "A_aesthetic_clinics", website_domain="vezeeta.com"),          # directory, not the merchant's site
        merchant(3, "B_custom_furniture"),                                          # no site
        merchant(4, "C_salla_zid_d2c", store_key="salla.sa/oud"),
        merchant(5, "B_custom_furniture", website_domain="gone.sa", exclusion_reason="B: no segment signal"),
        *zid,
    ]
    write(paths.INTERIM / "merchants.csv", merchants, MERCHANT_COLUMNS)
    sample = [{"record_id": "salla_zid_dork:salla.sa/oud", "store_key": "salla.sa/oud", "icp_label": "fit"},
              {"record_id": "salla_zid_dork:s0.zid.store", "store_key": "s0.zid.store", "icp_label": "fit"}]
    write(paths.SAMPLES / fingerprint.C_SAMPLE, sample, ["record_id", "store_key", "icp_label"])


def test_run_statuses_templates_contacts_and_manual_rows(tmp_path, monkeypatch):
    pages = {
        "https://www.clinic.sa": page("https://www.clinic.sa", html='<img data-src="/img/Tabby.svg"> اتصل 055 000 0001'),
        "https://salla.sa/oud": page("https://salla.sa/oud", 403),
        **{f"https://s{i}.zid.store": page(f"https://s{i}.zid.store", html=ZID_ICON) for i in range(5)},
    }
    pages["https://s1.zid.store"]["html"] += '<p>ادفع مع تمارا</p><a href="https://instagram.com/oud_s1">ig</a> 45.00 ر.س'
    setup(tmp_path, monkeypatch, pages)

    out = fingerprint.run(workers=2)
    rows = {r["merchant_id"]: r for r in out["rows"]}
    assert set(rows) == {"m_1", "m_2", "m_3", "m_4", "m_10", "m_11", "m_12", "m_13", "m_14"}   # excluded m_5 not fetched
    assert rows["m_1"]["bnpl_status"] == "tabby" and rows["m_1"]["final_url"] == "https://www.clinic.sa"   # https fell back to www
    assert rows["m_1"]["page_mobile"] is True and rows["m_1"]["evidence_kinds"] == "icon"
    assert rows["m_2"]["platform"] == "no_site" and rows["m_3"]["bnpl_status"] == ""
    assert rows["m_4"]["bnpl_status"] == "fetch_failed" and rows["m_4"]["page_phone"] == ""
    assert rows["m_10"]["bnpl_status"] == "not_detected" and "tabby2.svg" in rows["m_10"]["template_dropped"]   # 5/5 zid pages
    assert rows["m_11"]["bnpl_status"] == "competitor_only" and rows["m_11"]["currency_sar"] is True
    assert rows["m_10"]["page_instagram"] is False and rows["m_11"]["page_instagram"] is True           # zid.sa on 5 pages = hub
    check = {r["record_id"]: r for r in out["check"]}
    assert check["salla_zid_dork:salla.sa/oud"]["checked_by"] == "pending_manual"
    assert check["salla_zid_dork:s0.zid.store"]["contactable"] == "no"
    assert check["salla_zid_dork:s0.zid.store"]["bnpl_status"] == "not_detected"               # zid template icon dropped
    assert "Verdict pending" in out["summary"] and "0550000001" not in out["summary"]

    path = paths.SAMPLES / fingerprint.C_CHECK
    edited = list(csv.DictReader(path.open(encoding="utf-8")))
    edited[0].update(checked_by="manual_browser", phone_visible="no", whatsapp_visible="yes", instagram_visible="no",
                     bnpl_status="unclear")
    write(path, edited, fingerprint.C_CHECK_COLUMNS)
    again = fingerprint.run(workers=2)
    kept = {r["record_id"]: r for r in again["check"]}["salla_zid_dork:salla.sa/oud"]
    assert kept["checked_by"] == "manual_browser" and kept["contactable"] == "yes"
    assert "contactable_rate 0.50" in again["summary"] and "accept" in again["summary"]
    assert "share with a provider (unclear counted as yes) 0.50" in again["summary"] and "not hit" in again["summary"]


def test_manual_check_asks_only_missing_questions_and_can_stop(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "SAMPLES", tmp_path)
    base = {"platform": "salla", "icp_label": "fit", "http_status": "403", "phone_visible": "", "whatsapp_visible": "",
            "instagram_visible": "", "contactable": "", "note": "blocked"}
    rows = [{**base, "record_id": "r0", "store_url": "https://salla.sa/s0", "checked_by": "pending_manual", "bnpl_status": ""},
            {**base, "record_id": "r1", "store_url": "https://salla.sa/s1", "checked_by": "manual_browser",       # contacts done
             "phone_visible": "yes", "whatsapp_visible": "no", "instagram_visible": "no", "contactable": "yes", "bnpl_status": ""},
            {**base, "record_id": "r2", "store_url": "https://salla.sa/s2", "checked_by": "pending_manual", "bnpl_status": ""}]
    write(tmp_path / fingerprint.C_CHECK, rows, fingerprint.C_CHECK_COLUMNS)
    answers = iter(["n", "maybe", "y", "?",  "n", "y",      # r0: contacts + BNPL (Tamara)
                    "?", "n",                               # r1: BNPL only -> unclear
                    "y", "q"])                              # r2: stops, nothing saved
    opened = []
    out = fingerprint.manual_c_check(ask=lambda _: next(answers), open_url=opened.append)
    saved = {r["record_id"]: r for r in csv.DictReader((tmp_path / fingerprint.C_CHECK).open(encoding="utf-8"))}
    assert saved["r0"]["checked_by"] == "manual_browser" and saved["r0"]["contactable"] == "yes"
    assert saved["r0"]["instagram_visible"] == "unclear" and saved["r0"]["bnpl_status"] == "competitor_only"
    assert saved["r1"]["contactable"] == "yes" and saved["r1"]["bnpl_status"] == "unclear"
    assert saved["r2"]["checked_by"] == "pending_manual" and len(opened) == 3
    assert out == {"total": 3, "checked": 2, "contactable": 2, "bnpl_checked": 2}


def test_failure_reasons():
    import httpx
    from ksa_pipeline.web import error_label
    tls = httpx.ConnectError("[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: certificate has expired")
    dns = httpx.ConnectError("[Errno 8] nodename nor servname provided, or not known")
    assert error_label(tls) == "ConnectError:tls" and error_label(dns) == "ConnectError:dns"
    assert fingerprint.failure_reason("403", "") == "blocked for scripts"
    assert fingerprint.failure_reason(525, "") == "site broken: server or TLS error"
    assert fingerprint.failure_reason("0", "ConnectError:dns") == "site broken: domain does not resolve"


def test_text_phones_need_a_prefix():
    assert fingerprint.text_phones("sku 512345678, call +966 55 000 0001") == {("+966550000001", "mobile")}
    assert fingerprint.visible_text("<script>var t='0550000001'</script><p>hi</p>").strip() == "hi"


def test_contacts_in_embedded_json():
    html = '<script>{"social":{"wa":"https:\\/\\/wa.me\\/966550000001","ig":"https:\\/\\/instagram.com\\/oud.house"},"phone":"0550000002"}</script>'
    c = fingerprint.page_contacts(html, "https://s.zid.store")
    assert c["whatsapp"] == {"+966550000001"} and c["instagram"] == {"oud.house"} and c["mobile"] == {"+966550000002"}
