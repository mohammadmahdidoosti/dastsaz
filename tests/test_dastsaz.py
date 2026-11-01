import datetime as dt
import json
import random

import pytest

from dastsaz import analyze as A
from dastsaz import basalam, config as C, etsy, guard, pipeline


BAS_PRODUCT = {"id": 39072910, "name": "گردنبند نقره اسم دلخواه", "price": 1200000, "primaryPrice": 1500000,
               "rating": {"average": 4.8, "count": 6}, "sales_count": 80, "sales_count_week": 7,
               "categoryTitle": "گردنبند", "photo": {"MEDIUM": "https://statics.basalam.com/x.jpg"},
               "vendor": {"name": "نقره‌کاری", "owner": {"city": "اصفهان"}}}

ETSY_ITEM = {"listingId": "123", "name": "Dainty Gold Name Necklace", "url": "https://www.etsy.com/listing/123",
             "imageUrl": "https://i.etsystatic.com/a.jpg", "price": "24.50", "currency": "USD",
             "reviewCount": 1520, "boughtInLast24Hours": 12, "inCartCount": 30, "tags": ["name necklace"],
             "materials": ["gold", "silver"], "shop": "GoldShop"}


def test_guard_busy():
    assert guard.caravan_busy({"lanes": {"crawl": {"running": True}}})
    assert guard.caravan_busy({"lanes": {}, "autopilot": {"current": 20}})
    assert guard.caravan_busy({"lanes": {"site": {"running": True}}, "autopilot": {"current": None}}) == ""


def test_guard_off_by_default():
    assert C.GUARD is False and guard.check() == ""


def test_quiet_hours(monkeypatch):
    monkeypatch.setattr(C, "QUIET_FROM", 0)
    monkeypatch.setattr(C, "QUIET_TO", 9)
    tz = dt.timezone.utc
    assert guard.quiet_now(dt.datetime(2026, 1, 1, 3, tzinfo=tz))
    assert not guard.quiet_now(dt.datetime(2026, 1, 1, 12, tzinfo=tz))


def test_basalam_card_toman():
    c = basalam.card(BAS_PRODUCT, "گردنبند", 1)
    assert c["price_toman"] == 120000 and c["sales_week"] == 7 and c["image"].endswith("x.jpg")
    assert c["shop_city"] == "اصفهان"


class FakeResp:
    def __init__(self, data, code=200):
        self._d, self.status_code, self.text = data, code, json.dumps(data)

    def json(self):
        return self._d


class FakeSession:
    def __init__(self):
        self.calls = []

    def get(self, url, params=None, timeout=None):
        self.calls.append(params)
        n = params["size"]
        start = params["from"]
        return FakeResp({"products": [{**BAS_PRODUCT, "id": start + i} for i in range(n)]})


def test_basalam_fetch_slow_and_dedup():
    sleeps = []
    s = FakeSession()
    out = basalam.fetch(["الف", "ب"], 60, session=s, sleep=sleeps.append)
    assert len(s.calls) == 4 and all(params["sort"] == "sales" for params in s.calls)
    assert len(out) == 60                      # same ids in both queries -> kept once
    assert all(C.BASALAM_DELAY[0] <= x <= C.BASALAM_DELAY[1] for x in sleeps)


def test_etsy_card():
    c = etsy.card(ETSY_ITEM, "necklace")
    assert c["price_usd"] == 24.5 and c["price_toman"] == round(24.5 * C.USD_TOMAN)
    assert c["bought_24h"] == 12 and "gold" in c["materials"]


def test_etsy_needs_token():
    with pytest.raises(RuntimeError):
        etsy.Apify("")


class FakeAI:
    def post(self, url, json=None, timeout=None, headers=None):
        return FakeResp({"choices": [{"message": {"content": '{"name_fa":"گردنبند اسم طلایی","is_jewelry":true,'
                                                   '"type":"گردنبند","style":"اسم و حروف","material":"روکش طلا",'
                                                   '"color":"طلایی","personalized":true,"motif":"اسم","stone":""}'}}],
                         "usage": {"cost": 0.0002}})


def test_classify_and_unknown_values():
    p = etsy.card(ETSY_ITEM, "necklace")
    r = A.classify(p, "k", FakeAI())
    assert r["style"] == "اسم و حروف" and r["personalized"] and r["_cost"] == 0.0002
    assert A._pick("چیز عجیب", A.STYLES) == "سایر"


def test_popularity_order():
    a = etsy.card({**ETSY_ITEM, "boughtInLast24Hours": 1}, "x")
    b = etsy.card({**ETSY_ITEM, "boughtInLast24Hours": 20}, "x")
    assert A.top([a, b], 1)[0] is b


def test_pipeline_end_to_end(tmp_path, monkeypatch):
    monkeypatch.setattr(C, "DATA_DIR", tmp_path)
    monkeypatch.setattr(pipeline.guard, "wait_free", lambda **k: None)
    rnd = random.Random(1)
    bas = [basalam.card({**BAS_PRODUCT, "id": i, "sales_count_week": rnd.randint(0, 9),
                         "price": rnd.randint(3, 40) * 100000}, "q", i) for i in range(30)]
    ets = [etsy.card({**ETSY_ITEM, "listingId": str(i), "price": rnd.randint(10, 90),
                      "boughtInLast24Hours": rnd.randint(0, 20)}, "q") for i in range(30)]
    monkeypatch.setattr(pipeline.basalam, "fetch", lambda **k: bas)
    monkeypatch.setattr(pipeline.etsy, "fetch", lambda *a, **k: ets)
    calls = {"n": 0}

    def fake_all(items, key, progress=None):
        calls["n"] += 1
        styles = ["مینیمال", "بوهو", "اسم و حروف"]
        return [{**p, "name_fa": "نمونه", "is_jewelry": True, "type": "گردنبند", "style": styles[i % 3],
                 "material": "نقره", "color": "نقره‌ای", "personalized": i % 2 == 0, "motif": "قلب",
                 "stone": "", "_cost": 0.0002, "_error": ""} for i, p in enumerate(items)], 0.012
    monkeypatch.setattr(pipeline.A, "classify_all", fake_all)
    monkeypatch.setattr(pipeline.report, "insights", lambda st, key: (["نکته‌ی آزمایشی"], 0.001))

    def fake_search(q, size=30, session=None, sleep=None):
        return [basalam.card({**BAS_PRODUCT, "id": hash(q) % 1000 + i, "sales_count_week": 5}, q, i)
                for i in range(10)], 120
    monkeypatch.setattr(pipeline.O.basalam, "search", fake_search)
    monkeypatch.setattr(pipeline.O.basalam, "_session", lambda: None)
    monkeypatch.setattr(pipeline.O, "briefs", lambda items, key: ({0: {"i": 0, "name": "طرح آزمایشی", "brief": "ب"}}, 0.002))
    out = pipeline.run("t1")
    html = out.read_text(encoding="utf-8")
    assert "گزارش ترند" in html and "نکته‌ی آزمایشی" in html
    assert "لیست آزمایش این هفته" in html and "طرح آزمایشی" in html
    assert (tmp_path / "runs" / "t1" / "opportunities.csv").exists()
    assert (tmp_path / "runs" / "t1" / "products.csv").exists()
    pipeline.run("t1")                         # resume: no new AI calls
    assert calls["n"] == 1
    assert pipeline.runs()[0]["report"]


def test_etsy_rank_without_details():
    a = etsy.card({**ETSY_ITEM, "boughtInLast24Hours": None, "inCartCount": None, "reviewCount": 10, "position": 40}, "x")
    b = etsy.card({**ETSY_ITEM, "boughtInLast24Hours": None, "inCartCount": None, "reviewCount": 3000, "position": 5}, "x")
    assert A.top([a, b], 1)[0] is b


def test_insights_asks_without_reasoning(monkeypatch):
    from dastsaz import report
    sent = {}

    def fake_post(url, json=None, timeout=None, headers=None):
        sent.update(json)
        return FakeResp({"choices": [{"message": {"content": '{"points": ["الف", "ب"]}'}}], "usage": {"cost": 0.001}})
    monkeypatch.setattr(report.requests, "post", fake_post)
    st = report.stats([], [])
    pts, usd = report.insights(st, "k")
    assert pts == ["الف", "ب"] and sent["reasoning"] == {"enabled": False} and sent["max_tokens"] >= 4000


def test_seeds_and_signals():
    from dastsaz import opportunities as O
    bas = [{"motif": "طرح پاپیون", "sales_week": 9, "style": "فانتزی و بامزه", "material": "استیل"},
           {"motif": "پاپیون", "sales_week": 4, "style": "مینیمال", "material": "استیل"},
           {"motif": "بدون طرح", "sales_week": 50, "style": "مینیمال", "material": "استیل"}]
    ets = [{"motif": "گل", "style": "وینتیج", "material": "روکش طلا"} for _ in range(5)]
    sd = O.seeds(ets, bas)
    terms = [x["term"] for x in sd]
    assert terms[0] == "پاپیون" and "بدون طرح" not in terms and "وینتیج" in terms and "گل" in terms
    cards = [basalam.card({**BAS_PRODUCT, "id": i, "sales_count_week": 3, "sales_count": 20}, "q", i) for i in range(10)]
    o = O.signals({"q": "گوشواره پاپیون", "type": "گوشواره", "term": "پاپیون", "why": "", "source": "basalam"}, cards, 150)
    slow = [basalam.card({**BAS_PRODUCT, "id": i, "sales_count_week": 0, "sales_count": 200}, "q", i) for i in range(10)]
    quiet = [O.signals({"q": f"x{i}", "type": "گردنبند", "term": f"x{i}", "why": "", "source": "basalam"}, slow, 2000)
             for i in range(6)]
    crowded = O.signals({"q": "x", "type": "گردنبند", "term": "x", "why": "", "source": "basalam"}, cards, 9000)
    O.relabel([o, crowded] + quiet)
    assert o["week"] == 30 and "تقاضای زیاد، رقیب کم" in o["labels"] and "در حال اوج" in o["labels"]
    assert "رقابت سنگین" in crowded["labels"] and crowded not in O.pick([crowded])
    assert O.pick([crowded, o] + quiet)[0] is o
