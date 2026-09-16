"""Normalisation of KSA-specific identifiers: phones, URLs/platforms, handles, Arabic names."""
from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

# Eastern Arabic (U+0660..) and Persian (U+06F0..) digits -> ASCII
_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")


def to_ascii_digits(text: str) -> str:
    return text.translate(_DIGITS)


def normalize_phone(raw: object) -> tuple[str | None, str]:
    """Return (normalised number, phone_type).

    Handles +966 / 00966 / 966 / 0-prefixed / bare national formats and Arabic digits.
    Unified (9200xxxxx) and toll-free (800xxxxxxx) numbers are not E.164-dialable
    abroad, so they are returned in national form with their own type.
    """
    if raw is None or str(raw).strip() == "":
        return None, "none"
    digits = re.sub(r"\D", "", to_ascii_digits(str(raw)))
    if digits.startswith("00"):
        digits = digits[2:]
    if re.fullmatch(r"92\d{7}", digits):
        return digits, "unified"
    if re.fullmatch(r"800\d{7}", digits):
        return digits, "tollfree"
    if digits.startswith("966"):
        national = digits[3:]
    elif digits.startswith("0"):
        national = digits[1:]
    else:
        national = digits
    if re.fullmatch(r"5\d{8}", national):
        return "+966" + national, "mobile"
    if re.fullmatch(r"1[1-7]\d{7}", national):
        return "+966" + national, "landline"
    if not digits.startswith(("0", "966")) and 10 <= len(digits) <= 15:
        return "+" + digits, "foreign"
    return None, "invalid"


_PHONE_CANDIDATE = re.compile(r"(?:\+|00)?\d[\d\s\-]{7,16}\d")


def extract_phones(text: str | None) -> list[tuple[str, str]]:
    """All valid phones found in free text (bio, captions), deduplicated, order kept."""
    if not text:
        return []
    seen: dict[str, str] = {}
    for match in _PHONE_CANDIDATE.findall(to_ascii_digits(text)):
        number, kind = normalize_phone(match)
        if number and number not in seen:
            seen[number] = kind
    return list(seen.items())


def best_phone(candidates: list[tuple[str | None, str]]) -> tuple[str | None, str]:
    """Prefer mobile (most likely the owner) > landline > unified > anything valid."""
    rank = {"mobile": 0, "landline": 1, "unified": 2, "tollfree": 3, "foreign": 4}
    valid = [c for c in candidates if c[0]]
    if not valid:
        return None, "none"
    return sorted(valid, key=lambda c: rank.get(c[1], 9))[0]


_IG_RESERVED = {"p", "reel", "reels", "explore", "stories", "tv", "accounts", "direct"}
_SOCIAL_HOSTS = ("snapchat.com", "tiktok.com", "facebook.com", "x.com", "twitter.com", "youtube.com")
_LINK_HUBS = ("linktr.ee", "beacons.ai", "bio.link", "linkin.bio")


def parse_web(url: object) -> dict:
    """Classify a URL into platform + identifiers.

    Returns keys: website_domain, website_platform, store_key, instagram_handle,
    whatsapp_phone. Store URL patterns for Salla/Zid are verified on Day 1 samples.
    """
    out = {"website_domain": None, "website_platform": "none", "store_key": None,
           "instagram_handle": None, "whatsapp_phone": None}
    if url is None or str(url).strip() == "":
        return out
    u = str(url).strip()
    if not re.match(r"^[a-z][a-z0-9+.-]*://", u, re.I):
        u = "https://" + u
    parsed = urlparse(u)
    host = (parsed.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    path = [seg for seg in parsed.path.split("/") if seg]

    if host.endswith("instagram.com"):
        out["website_platform"] = "instagram"
        if path and path[0].lower() not in _IG_RESERVED:
            out["instagram_handle"] = path[0].lower()
    elif host in ("wa.me", "api.whatsapp.com", "whatsapp.com", "web.whatsapp.com"):
        out["website_platform"] = "whatsapp"
        raw_phone = parse_qs(parsed.query).get("phone", [None])[0] or (path[0] if path else None)
        out["whatsapp_phone"] = normalize_phone(raw_phone)[0]
    elif host == "salla.sa" or host.endswith(".salla.sa"):
        out["website_platform"] = "salla"
        out["store_key"] = host if host != "salla.sa" else (f"salla.sa/{path[0].lower()}" if path else None)
    elif host.endswith("zid.store"):
        out["website_platform"] = "zid"
        out["store_key"] = host
    elif host.endswith(_LINK_HUBS):
        out["website_platform"] = "linktree"
    elif host.endswith(_SOCIAL_HOSTS):
        out["website_platform"] = "social"
    elif host:
        out["website_platform"] = "own_site"
        out["website_domain"] = host
    return out


_IG_IN_TEXT = re.compile(r"(?:instagram\.com/|(?<![\w.])@)([A-Za-z0-9._]{2,30})")


def instagram_handle_from_text(text: str | None) -> str | None:
    if not text:
        return None
    for handle in _IG_IN_TEXT.findall(text):
        handle = handle.rstrip(".").lower()
        if handle not in _IG_RESERVED:
            return handle
    return None


_TASHKEEL = re.compile(r"[\u064B-\u0652\u0670\u0640]")  # diacritics + tatweel
_AR_MAP = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ة": "ه", "ى": "ي", "ؤ": "و", "ئ": "ي"})
_NOISE = re.compile(r"[^\w\s]|_")
_GENERIC = {"clinic", "clinics", "center", "centre", "co", "llc", "est", "عياده", "عيادات", "مركز", "مؤسسه", "شركه"}
# Branch suffixes: "X - Olaya Branch", "X | فرع العليا", "X (Olaya)" -> "X"
_BRANCH_CUT = re.compile(r"\s[-|–—]\s.*$|\(.*$|\bbranch\b.*$|\sفرع\s.*$", re.I)


def name_key(name: str | None) -> str | None:
    """Normalised business name for chain detection and fuzzy dedupe.

    Removes Arabic diacritics/tatweel, unifies alef/ta-marbuta/ya forms,
    lowercases Latin, drops punctuation and generic words (clinic, مركز, فرع ...).
    """
    if not name:
        return None
    s = _BRANCH_CUT.sub("", to_ascii_digits(name).strip()).lower()
    s = _TASHKEEL.sub("", s).translate(_AR_MAP)
    s = _NOISE.sub(" ", s)
    tokens = [t for t in s.split() if t not in _GENERIC and not t.isdigit()]
    return " ".join(tokens) or None


def mask_phone(phone: str | None) -> str | None:
    """+966551234567 -> +9665•••••567 (for committed samples)."""
    if not phone:
        return phone
    keep_head = 5 if phone.startswith("+966") else 2
    return phone[:keep_head] + "•" * max(len(phone) - keep_head - 3, 0) + phone[-3:]
