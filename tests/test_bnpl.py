import httpx

from ksa_pipeline import paths, web
from ksa_pipeline.bnpl import context, detect, discover, markers


def test_detect_statuses():
    tabby = '<script src="https://checkout.tabby.ai/tabby-promo.js"></script><img src="/tamara-logo.svg">'
    assert detect(tabby)["bnpl_status"] == "tabby"
    assert detect('<script src="https://cdn.tamara.co/widget/tamara-widget.js"></script>')["bnpl_status"] == "competitor_only"
    assert detect("<p>امكانية التقسيط على دفعات</p>")["bnpl_status"] == "generic_installment"
    assert detect("<p>A tabby cat, تم الدفع: مدفوع</p>")["bnpl_status"] == "not_detected"   # ambiguous words alone do not count


def test_arabic_text_is_whole_word():
    assert detect("<div>ابل باي, بطاقة الائتمان, تابي, تمارا</div>")["providers"] == ["tabby", "tamara"]
    assert detect("<p>ادفع بتابي أو وتمارا</p>")["providers"] == ["tabby", "tamara"]           # prefixes ب و
    assert detect("<p>اختبار كتابي وتعليم كتابية</p>")["bnpl_status"] == "not_detected"         # كتابي is not تابي


def test_payment_icons_count_with_kind():
    ram = '<img src="/web/assets/images/Tabby.svg?v=1"><img src="/web/assets/images/tamara.svg?v=1"><p>تقسيط</p>'
    d = detect(ram)
    assert d["bnpl_status"] == "tabby" and d["generic_installment"]
    assert "tabby:icon:/web/assets/images/Tabby.svg?v=1" in d["evidence"]
    zid = '<img src="https://media.zid.store/cdn-cgi/image/h=80,q=100/https://media.zid.store/static/tamara2.svg">'
    assert detect(zid)["evidence"][0].startswith("tamara:icon:")
    assert detect('<a href="/pages/tabby">about</a><script src="/tabby-promo.js">')["bnpl_status"] == "not_detected"


def test_markers_verified_kinds_exist():
    for name, m in markers()["providers"].items():
        assert set(m["verified"]) <= {"html", "icon", "text_ar", "text_en"} and all(k in m for k in m["verified"]), name


def test_discover_and_context_mask_digits():
    html = ('<img src="https://cdn.example/payments/tabby.png"> call 0550000001 and pay with tabby.ai now'
            '<meta content="Shop now. Pay later with tabby">')
    assert discover(html) == ["https://cdn.example/payments/tabby.png"]                  # prose in content= is skipped
    assert all("0550000001" not in s for s in context(html, "tabby.ai"))
    snips = context("<p>كتابي ... تابي</p>", "تابي", width=4, word=True)
    assert len(snips) == 1 and "كتابي" not in snips[0]


def test_fetch_caches_and_reports_failures(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "DATA", tmp_path)
    calls = []
    def handler(request):
        calls.append(str(request.url))
        if "down" in str(request.url):
            return httpx.Response(503)
        return httpx.Response(200, text="<html>tabby.ai</html>")
    client = httpx.Client(transport=httpx.MockTransport(handler))
    ok = web.fetch("https://shop.example/", client=client)
    assert ok["ok"] and "tabby.ai" in ok["html"]
    again = web.fetch("https://shop.example/", client=client)        # served from cache
    assert again["html"] == ok["html"] and len(calls) == 1
    down = web.fetch("https://down.example/", client=client)
    assert down["ok"] is False and down["status"] == 503 and down["html"] == ""
    web.fetch("https://down.example/", client=client)                  # transient failure is not cached
    assert calls.count("https://down.example/") == 2
