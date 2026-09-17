from ksa_pipeline import fingerprint, paths, scoring
from ksa_pipeline.resolve import MERCHANT_COLUMNS


def write(path, rows, fields):
    fingerprint.write_csv(path, rows, fields)


def merchant(mid, seg, **kw):
    m = {c: "" for c in MERCHANT_COLUMNS}
    m.update(merchant_id=mid, segment=seg, cities="riyadh", name=mid, phone_type="none", contactable="False",
             reviews_count="0", rating="", n_locations="1")
    m.update(kw)
    return m


def setup(tmp_path, monkeypatch):
    for d in ("interim", "samples"):
        (tmp_path / d).mkdir()
    monkeypatch.setattr(paths, "INTERIM", tmp_path / "interim")
    monkeypatch.setattr(paths, "SAMPLES", tmp_path / "samples")
    merchants = [
        merchant("a1", "A_aesthetic_clinics", phone_type="mobile", contactable="True", reviews_count="500", rating="4.8", n_locations="3"),
        merchant("a2", "A_aesthetic_clinics", contactable="True", reviews_count="40", rating="4.1"),           # WhatsApp link only
        merchant("a3", "A_aesthetic_clinics", instagram_handle="clinic", contactable="True", reviews_count="10", rating="3.9"),
        merchant("a4", "A_aesthetic_clinics", phone_type="landline", reviews_count="5"),
        merchant("a5", "A_aesthetic_clinics", phone_type="mobile", contactable="True", reviews_count="900"),    # tabby
        merchant("a6", "A_aesthetic_clinics", exclusion_reason="A: hospital or enterprise group"),
        merchant("b1", "B_custom_furniture", phone_type="mobile", contactable="True", reviews_count="30", rating="4.5", cities="jeddah"),
        merchant("b2", "B_custom_furniture", reviews_count="3"),                                               # contact on the page only
        merchant("c1", "C_salla_zid_d2c"),
    ]
    write(tmp_path / "interim" / "merchants.csv", merchants, MERCHANT_COLUMNS)
    web = []
    for mid, status, extra in [("a1", "not_detected", {}), ("a2", "competitor_only", {}), ("a3", "fetch_failed", {}),
                               ("a5", "tabby", {}), ("b2", "not_detected", {"page_whatsapp": "True"})]:
        w = {c: "" for c in fingerprint.WEB_COLUMNS}
        w.update(merchant_id=mid, bnpl_status=status, **extra)
        web.append(w)
    write(tmp_path / "interim" / "bnpl.csv", web, fingerprint.WEB_COLUMNS)
    write(tmp_path / "samples" / fingerprint.QA_TABBY,
          [{"merchant_id": "a5", "segment": "A_aesthetic_clinics", "url": "u", "evidence_kinds": "icon", "manual_answer": "yes",
            "checked_on": "", "adjudication": "", "adjudication_note": ""}], fingerprint.QA_TABBY_COLUMNS)
    write(tmp_path / "interim" / "enrich.csv",
          [{"merchant_id": "a1", "owner_name_in_source": "True", "input_kind": "page_text"}], ["merchant_id", "owner_name_in_source", "input_kind"])


def test_points_exclusions_and_channels(tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch)
    rows = {r["merchant_id"]: r for r in scoring.build()}
    assert rows["a5"]["score_exclusion"] == "already Tabby merchant"
    assert rows["a6"]["score_exclusion"].startswith("A: hospital") and rows["c1"]["score_exclusion"].startswith("segment rejected")
    a1 = rows["a1"]
    assert a1["channel"] == "mobile_or_whatsapp_and_name" and a1["reachability_points"] == 20 and a1["hook_from_page"]
    assert a1["ticket_points"] == 30 and a1["bnpl_points"] == 25 and a1["reviews_quartile"] == 4
    assert a1["traction_points"] == 10 + 8 + 7 and a1["score"] == 30 + 25 + 25 + 20 and a1["tier"] == "A"
    assert rows["a2"]["channel"] == "mobile_or_whatsapp" and rows["a2"]["bnpl_points"] == 15     # Maps WhatsApp link = mobile
    assert rows["a3"]["channel"] == "instagram" and rows["a3"]["bnpl_status_final"] == "unchecked" and rows["a3"]["bnpl_points"] == 18
    assert rows["a4"]["channel"] == "other_phone" and not rows["a4"]["direct_channel"]
    assert rows["b2"]["channel"] == "mobile_or_whatsapp"                                           # WhatsApp found on the homepage
    assert "B Jeddah" in rows["b1"]["flags"] and "medical" in rows["a1"]["flags"]
    assert rows["b1"]["reviews_quartile"] == 4                                                     # quartiles within the segment


def test_tabby_false_positive_is_scored(tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch)
    qa = [{"merchant_id": "a5", "segment": "A_aesthetic_clinics", "url": "u", "evidence_kinds": "icon", "manual_answer": "no",
           "checked_on": "", "adjudication": "false_positive", "adjudication_note": ""}]
    write(tmp_path / "samples" / fingerprint.QA_TABBY, qa, fingerprint.QA_TABBY_COLUMNS)
    a5 = {r["merchant_id"]: r for r in scoring.build()}["a5"]
    assert a5["score_exclusion"] == "" and a5["bnpl_status_final"] == "not_detected"


def test_run_top_list_sensitivity_and_no_contacts_in_output(tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch)
    out = scoring.run()
    top = sorted(out["top"], key=lambda r: r["top_rank"])
    assert all(r["tier"] == "A" and r["direct_channel"] for r in top) and top[0]["merchant_id"] == "a1"
    assert len(out["sensitivity"]) == 4 * 2 + 2 and all(0 <= v["overlap"] <= 1 for v in out["sensitivity"])
    header = (tmp_path / "interim" / "scored.csv").read_text(encoding="utf-8").splitlines()[0]
    assert "phone" not in header and "owner_name_inferred" not in header
    assert "Sensitivity" in (tmp_path / "samples" / "scoring_summary.md").read_text(encoding="utf-8")


def test_tier_cuts_follow_the_maximum():
    cfg = scoring.config()
    assert scoring.max_points(cfg) == 100 and scoring.tier_cuts(cfg) == {"A": 82.5, "B": 65.0}
    assert scoring.tier_cuts(scoring.scaled(cfg, "ticket_fit", 0.8)) == {"A": round(0.825 * 94, 2), "B": round(0.65 * 94, 2)}


def test_reserve_flag_for_ties_at_cutoff(tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch)
    m = fingerprint.read_csv(tmp_path / "interim" / "merchants.csv")
    twin = dict(next(r for r in m if r["merchant_id"] == "a1"), merchant_id="a7", reviews_count="400")
    write(tmp_path / "interim" / "merchants.csv", m + [twin], MERCHANT_COLUMNS)
    web = fingerprint.read_csv(tmp_path / "interim" / "bnpl.csv")
    web.append(dict(next(r for r in web if r["merchant_id"] == "a1"), merchant_id="a7"))
    write(tmp_path / "interim" / "bnpl.csv", web, fingerprint.WEB_COLUMNS)
    write(tmp_path / "interim" / "enrich.csv", [{"merchant_id": x, "owner_name_in_source": "True", "input_kind": "page_text"} for x in ("a1", "a7")],
          ["merchant_id", "owner_name_in_source", "input_kind"])
    import copy
    cfg = copy.deepcopy(scoring.config())
    cfg["top_list"]["size"] = 1
    rows = {r["merchant_id"]: r for r in scoring.build(cfg)}
    assert rows["a1"]["score"] == rows["a7"]["score"] and rows["a1"]["top_rank"] == 1           # more reviews wins the tie
    assert "reserve" in rows["a7"]["flags"] and "reserve" not in rows["a1"]["flags"]
