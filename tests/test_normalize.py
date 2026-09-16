import pytest

from ksa_pipeline.normalize import extract_phones, instagram_handle_from_text, mask_phone, name_key, normalize_phone, parse_web


@pytest.mark.parametrize("raw,expected", [
    ("+966 55 000 0001", ("+966550000001", "mobile")),
    ("00966550000001", ("+966550000001", "mobile")),
    ("0550000001", ("+966550000001", "mobile")),
    ("550000001", ("+966550000001", "mobile")),
    ("٠٥٥٠٠٠٠٠٠١", ("+966550000001", "mobile")),        # Eastern Arabic digits
    ("011 000 0002", ("+966110000002", "landline")),
    ("920000003", ("920000003", "unified")),
    ("8001234567", ("8001234567", "tollfree")),
    ("+971 50 123 4567", ("+971501234567", "foreign")),
    ("123", (None, "invalid")),
    ("", (None, "none")),
    (None, (None, "none")),
])
def test_normalize_phone(raw, expected):
    assert normalize_phone(raw) == expected


def test_extract_phones_from_arabic_bio():
    bio = "للحجز واتساب ٠٥٥ ٠٠٠ ٠٠٠١ او اتصل 0110000002"
    assert extract_phones(bio) == [("+966550000001", "mobile"), ("+966110000002", "landline")]


@pytest.mark.parametrize("url,platform,key,value", [
    ("https://www.instagram.com/Alreem.Smile/?hl=en", "instagram", "instagram_handle", "alreem.smile"),
    ("instagram.com/p/xyz", "instagram", "instagram_handle", None),
    ("https://wa.me/966550000004", "whatsapp", "whatsapp_phone", "+966550000004"),
    ("https://api.whatsapp.com/send?phone=0550000004", "whatsapp", "whatsapp_phone", "+966550000004"),
    ("https://oudhouse.salla.sa/", "salla", "store_key", "oudhouse.salla.sa"),
    ("https://salla.sa/oudhouse", "salla", "store_key", "salla.sa/oudhouse"),
    ("https://abaya.zid.store", "zid", "store_key", "abaya.zid.store"),
    ("https://linktr.ee/brand", "linktree", "website_domain", None),
    ("www.Clinic-Example.sa/ar/about", "own_site", "website_domain", "clinic-example.sa"),
    ("", "none", "website_domain", None),
])
def test_parse_web(url, platform, key, value):
    out = parse_web(url)
    assert out["website_platform"] == platform
    assert out[key] == value


def test_instagram_handle_from_text():
    assert instagram_handle_from_text("تابعونا @Oud.House_KSA.") == "oud.house_ksa"
    assert instagram_handle_from_text("email info@clinic.sa") is None


def test_name_key_unifies_arabic_forms_and_generic_words():
    assert name_key("عِيادة ابتسامة الريم") == name_key("عياده ابتسامه الريم")
    assert name_key("Smile Dental Center - Olaya Branch") == "smile dental"
    assert name_key("Smile Dental Center (Olaya)") == "smile dental"
    assert name_key("مركز ابتسامة الريم فرع الملقا") == name_key("ابتسامة الريم")


def test_mask_phone():
    assert mask_phone("+966550000001") == "+9665•••••001"
