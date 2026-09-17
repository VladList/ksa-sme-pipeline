from pathlib import Path

from ksa_pipeline.ingest import ingest
from ksa_pipeline.pii import find_mobiles
from ksa_pipeline.schema import columns, contract_violations, pii_columns

FIXTURE = Path(__file__).parent / "fixtures" / "google_maps_sample.json"


def test_all_configs_parse():
    import yaml
    from ksa_pipeline.paths import CONFIG, SOURCES_YAML
    for path in [*CONFIG.glob("*.yaml"), SOURCES_YAML]:
        assert yaml.safe_load(path.read_text(encoding="utf-8")), path


def test_schema_contract_holds():
    assert contract_violations() == []
    assert {"phone_e164", "owner_name_inferred", "text_blob"} <= pii_columns()


def test_google_maps_ingest():
    rows = {r["record_id"]: r for r in ingest("google_maps", FIXTURE)}
    assert len(rows) == 3                                   # duplicate placeId merged
    reem = rows["google_maps:ChIJ_fake_1"]
    assert reem["segment"] == "A_aesthetic_clinics"
    assert reem["query"] == "عيادة تقويم أسنان | ابتسامة هوليود"
    assert (reem["phone_e164"], reem["phone_type"]) == ("+966550000001", "mobile")
    assert reem["instagram_handle"] == "alreem.smile"
    closed = rows["google_maps:ChIJ_fake_3"]
    assert closed["is_closed"] is True
    assert closed["phone_type"] == "mobile"                 # WhatsApp mobile beats unified number
    assert closed["has_whatsapp_link"] is True
    assert set(rows["google_maps:ChIJ_fake_2"]) == set(columns("ingest"))
    assert reem["name_location_count"] == 1                 # merged duplicate is not a second location
    assert rows["google_maps:ChIJ_fake_2"]["name_location_count"] == 2   # "Smile Dental Center" x2 branches


def test_pii_guard():
    assert find_mobiles("call +966 55 000 0001") == ["+966550000001"]
    assert find_mobiles("masked +9665•••••001, landline 0110000002") == []
    # regression 2026-09-17: a row ending in "5" glued onto the next row's date "2026-09-17"
    assert find_mobiles("drop,fit 4 < 5\n2026-09-17,A,riyadh_circle") == []
    assert find_mobiles("fit 5 2026-09-17") == []
    assert find_mobiles("call 055-000-0001") == ["0550000001"]


def test_url_list_ingest_keeps_title_and_merges_pages_of_one_store(tmp_path):
    raw = tmp_path / "2026-09-17__dork.csv"
    raw.write_text(
        "url,query,title,segment,found_on\n"
        '"https://tharwa.zid.store/","site:zid.store x","Tharwa perfumes",C_salla_zid_d2c,2026-09-17\n'
        '"https://tharwa.zid.store/products/abc","site:zid.store x","Tharwa product",C_salla_zid_d2c,2026-09-17\n'
        '"https://salla.sa/nife.3od","site:salla.sa x","Nife oud",C_salla_zid_d2c,2026-09-17\n',
        encoding="utf-8")
    rows = {r["record_id"]: r for r in ingest("salla_zid_dork", raw)}
    assert set(rows) == {"salla_zid_dork:tharwa.zid.store", "salla_zid_dork:salla.sa/nife.3od"}
    assert rows["salla_zid_dork:tharwa.zid.store"]["name"] == "Tharwa perfumes"
    assert rows["salla_zid_dork:salla.sa/nife.3od"]["phone_type"] == "none"
