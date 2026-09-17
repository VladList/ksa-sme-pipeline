from ksa_pipeline.resolve import MERCHANT_COLUMNS, resolve
from ksa_pipeline.rules import exclusion_reasons
from ksa_pipeline.schema import columns


def rec(i, **kw):
    r = {c: "" for c in columns("ingest")}
    r.update(record_id=f"google_maps:p{i}", source_id="google_maps", run_id="2026-09-17__full_A_aesthetic_clinics__riyadh",
             segment="A_aesthetic_clinics", name=f"Dental clinic {i}", category_raw="Dental clinic",
             google_place_id=f"p{i}", phone_type="none", is_closed="False", has_whatsapp_link="False", reviews_count="10")
    r.update(kw)
    return r


def test_shared_domain_merges_branches_and_counts_locations():
    records = [rec(1, website_domain="josephderm.com", name="JosephDerm Yarmouk"),
               rec(2, website_domain="josephderm.com", name="JosephDerm Rawdah"),
               rec(3, website_domain="other.sa")]
    merchants, stats = resolve(records)
    assert stats["merchants"] == 2 and stats["merged_groups"] == 1
    joseph = next(m for m in merchants if m["website_domain"] == "josephderm.com")
    assert joseph["n_locations"] == 2 and joseph["n_records"] == 2
    assert set(joseph) == set(MERCHANT_COLUMNS)


def test_hub_identifier_and_ignored_domain_do_not_link():
    shared_phone = [rec(i, phone_e164="+966110000000", phone_type="landline") for i in range(13)]   # 13 > hub_max_records 12
    shared_host = [rec(100, website_domain="sites.google.com"), rec(101, website_domain="sites.google.com")]
    merchants, stats = resolve(shared_phone + shared_host)
    assert stats["merchants"] == 15
    assert "phone_e164:+966110000000" in stats["hub_identifiers_ignored"]


def test_chain_and_contactable():
    branches = [rec(i, instagram_handle="bigchain") for i in range(7)]
    merchants, _ = resolve(branches)
    assert len(merchants) == 1
    assert merchants[0]["exclusion_reason"].startswith("chain: 7 locations")
    assert merchants[0]["contactable"] is True


def test_segment_rules():
    assert exclusion_reasons("A_aesthetic_clinics", "Pioneer care clinic", {"Specialized clinic"}) == ["A: no segment signal in name or category"]
    assert exclusion_reasons("A_aesthetic_clinics", "Lines Clinics", {"Skin care clinic"}) == []
    assert "A: hospital or enterprise group" in exclusion_reasons("A_aesthetic_clinics", "Dr. Sulaiman Al Habib Dermatology", {"Dermatologist"})
    assert exclusion_reasons("B_custom_furniture", "تفصيل ستائر و مجالس", set()) == []
    assert exclusion_reasons("B_custom_furniture", "Miro Furniture", {"Furniture store"}) == ["B: no segment signal in name or category"]
    assert exclusion_reasons("C_salla_zid_d2c", "رند البحرين", set(), "salla.sa/rend-bahrain.com") == ["C: outside KSA signal"]
    assert exclusion_reasons("C_salla_zid_d2c", "اكبر متجر عطور باسعار الجمله", set()) == ["C: wholesale"]
    assert exclusion_reasons("C_salla_zid_d2c", "تميم للعطور", set(), "tmymllatwr.zid.store") == []
