import hashlib
import json

import httpx

from ksa_pipeline import enrich, fingerprint, paths
from ksa_pipeline.resolve import MERCHANT_COLUMNS


def write(path, rows, fields):
    fingerprint.write_csv(path, rows, fields)


def setup(tmp_path, monkeypatch):
    for d in ("interim", "samples", "cache/web"):
        (tmp_path / d).mkdir(parents=True)
    monkeypatch.setattr(paths, "DATA", tmp_path)
    monkeypatch.setattr(paths, "INTERIM", tmp_path / "interim")
    monkeypatch.setattr(paths, "SAMPLES", tmp_path / "samples")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    merchants = []
    for mid, seg, name, excl in [("m1", "A_aesthetic_clinics", "عيادة د. سارة", ""), ("m2", "B_custom_furniture", "Sofa workshop", ""),
                                 ("m3", "A_aesthetic_clinics", "Tabby clinic", ""), ("m4", "C_salla_zid_d2c", "oud", ""),
                                 ("m5", "A_aesthetic_clinics", "Hospital", "A: hospital")]:
        m = {c: "" for c in MERCHANT_COLUMNS}
        m.update(merchant_id=mid, segment=seg, name=name, exclusion_reason=excl, categories="Dentist", cities="riyadh")
        merchants.append(m)
    write(tmp_path / "interim" / "merchants.csv", merchants, MERCHANT_COLUMNS)
    web = [{c: "" for c in fingerprint.WEB_COLUMNS} for _ in range(3)]
    web[0].update(merchant_id="m1", target_url="https://clinic.sa", bnpl_status="not_detected")
    web[1].update(merchant_id="m2", bnpl_status="")
    web[2].update(merchant_id="m3", target_url="https://t.sa", bnpl_status="tabby")
    write(tmp_path / "interim" / "bnpl.csv", web, fingerprint.WEB_COLUMNS)
    key = hashlib.sha1("https://www.clinic.sa".encode()).hexdigest()                       # page cached under the www variant
    (tmp_path / "cache" / "web" / f"{key}.json").write_text(json.dumps({"ok": True}), encoding="utf-8")
    (tmp_path / "cache" / "web" / f"{key}.html").write_text(
        "<script>x</script><h1>المديرة الطبية: د. سارة أحمد</h1><p>تنظيف 250 ريال، اتصل 0550000001</p>", encoding="utf-8")


def fake_api(calls, answer):
    def handler(request):
        calls.append(json.loads(request.content))
        body = {"choices": [{"finish_reason": "stop", "message": {"content": json.dumps(answer)}}],
                "usage": {"prompt_tokens": 1000, "completion_tokens": 500}}
        return httpx.Response(200, json=body)
    return httpx.MockTransport(handler)


ANSWER = {"owner_name_inferred": "د. سارة أحمد", "owner_role_inferred": "medical_director",
          "owner_evidence_inferred": "المديرة الطبية: د. سارة أحمد", "ticket_sar_min_inferred": 250,
          "ticket_sar_max_inferred": 3000, "ticket_basis_inferred": "prices_on_page",
          "hook_ar_inferred": "مرحبا د. سارة أحمد، هل يفيد تقسيط التنظيف لعملائكم؟", "hook_fact_inferred": "cleaning for 250 SAR"}


def test_candidates_skip_tabby_c_and_excluded_and_mask_phones(tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch)
    pool = enrich.candidates()
    assert [c["merchant_id"] for c in pool] == ["m1", "m2"]                                  # m3 tabby (no QA row), m4 C, m5 excluded
    assert "0550000001" not in pool[0]["page_text"] and "[phone]" in pool[0]["page_text"]
    assert "<script>" not in pool[0]["page_text"] and pool[1]["page_text"] == ""


def test_run_verbatim_check_cache_and_review(tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch)
    calls = []
    out = enrich.run(transport=fake_api(calls, ANSWER))
    assert len(calls) == 2 and calls[0]["response_format"]["json_schema"]["strict"] is True
    assert "0550000001" not in json.dumps(calls, ensure_ascii=False)
    rows = {r["merchant_id"]: r for r in fingerprint.read_csv(tmp_path / "interim" / "enrich.csv")}
    assert rows["m1"]["owner_name_in_source"] == "True" and rows["m2"]["owner_name_in_source"] == "False"   # m2 text lacks the name
    assert out["cost_this_run_usd"] == round(2 * (1000 / 1e6 * 0.20 + 500 / 1e6 * 1.20), 4)
    assert out["g3_by_segment"]["A_aesthetic_clinics"] == {"merchants": 1, "contactable": 0, "owner_name_verified": 1,
                                                           "name_and_contactable": 0, "hook_from_page": 1, "price_on_page": 1}
    again = enrich.run(transport=fake_api(calls, ANSWER))
    assert len(calls) == 2 and again["cost_this_run_usd"] == 0                               # served from data/cache/llm
    review = "\n".join(enrich.review_lines(list(rows.values())))
    assert "سارة أحمد" not in review and "[owner]" in review
    assert "سارة" not in (tmp_path / "samples" / "enrich_summary.md").read_text(encoding="utf-8")


def test_budget_stop_and_errors_not_cached(tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch)
    cfg = dict(enrich.config())
    cfg["budget_usd"] = 0.0000001
    monkeypatch.setattr(enrich, "config", lambda: cfg)
    calls = []
    enrich.run(workers=1, transport=fake_api(calls, ANSWER))
    assert len(calls) == 1                                                                   # stopped after the first paid call
    failing = httpx.MockTransport(lambda r: httpx.Response(400, json={"error": {"message": "bad model"}}))
    cfg["budget_usd"] = 5
    out = enrich.run(transport=failing)
    assert out["answered"] == 1 and "HTTP 400" in str(out["errors"])                         # m1 cached, m2 error, not cached


def test_trial_pick_is_stratified():
    pool = [{"merchant_id": f"t{i}", "page_text": "x"} for i in range(5)] + [{"merchant_id": f"n{i}", "page_text": ""} for i in range(50)]
    chosen = enrich.pick(pool, 20, 42)
    assert len(chosen) == 20 and sum(bool(c["page_text"]) for c in chosen) == 5              # all 5 with text, 15 name only
    assert chosen == enrich.pick(pool, 20, 42)                                              # same seed, same sample


def test_review_masks_partial_owner_names():
    row = {"merchant_id": "m", "segment": "A", "input_kind": "page_text", "input_chars": 1, "owner_name_inferred": "د. سارة أحمد",
           "owner_role_inferred": "owner", "owner_name_in_source": True, "ticket_sar_min_inferred": "", "ticket_sar_max_inferred": "",
           "ticket_basis_inferred": "unknown", "output_tokens": 1, "error": "", "hook_fact_inferred": "f",
           "hook_ar_inferred": "مرحبا دكتورة سارة، رقمنا 0550000001"}
    line = enrich.review_lines([row])[0]
    assert "سارة" not in line and "0550000001" not in line
