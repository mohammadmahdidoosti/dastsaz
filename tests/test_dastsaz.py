import datetime as dt
import json
import random

import pytest

from dastsaz import analyze as A
from dastsaz import basalam, config as C, digikala, etsy, guard, pipeline, trends


BAS_PRODUCT = {"id": 39072910, "name": "گردنبند نقره اسم دلخواه", "price": 1200000, "primaryPrice": 1500000,
               "rating": {"average": 4.8, "count": 6}, "sales_count": 80, "sales_count_week": 7,
               "categoryTitle": "گردنبند", "photo": {"MEDIUM": "https://statics.basalam.com/x.jpg"},
               "vendor": {"name": "نقره‌کاری", "owner": {"city": "اصفهان"}}}

DK_PRODUCT = {"id": 18411251, "title_fa": "گردنبند زنانه مدل پاپیون", "rating": {"rate": 81.3, "count": 555},
              "url": {"uri": "/product/dkp-18411251/گردنبند-پاپیون"},
              "images": {"main": {"url": ["https://dkstatics-public.digikala.com/a.jpg?x-oss-process=resize"]}},
              "default_variant": {"price": {"selling_price": 6990000}},
              "data_layer": {"brand": "متفرقه", "item_category5": "زیورآلات زنانه"}}

TR_ITEM = {"keyword": "گردنبند اسم", "averageInterest": 40, "latestInterest": 55, "yoyChangePct": 22.5,
           "seasonality": {"isSeasonal": True, "peakMonths": [12, 2], "nextPeakDate": "2026-12-15",
                           "publishBy": "2026-11-20"},
           "risingQueries": [{"query": "گردنبند اسم انگلیسی", "formattedValue": "+250%"}, "قیمت دلار"],
           "breakoutQueries": [{"query": "گردنبند اسم انگلیسی", "value": "Breakout"}],
           "trendsUrl": "https://trends.google.com/trends/explore?geo=IR&q=x"}

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
    dk = [digikala.card({**DK_PRODUCT, "id": 500 + i}, "گردنبند", i + 1) for i in range(12)]
    monkeypatch.setattr(pipeline.digikala, "fetch", lambda **k: dk)
    monkeypatch.setattr(pipeline.O.digikala, "search", lambda q, session=None, sleep=None: (dk[:10], 60))
    monkeypatch.setattr(pipeline.O.digikala, "_session", lambda: None)
    tr_rows = [trends.row(TR_ITEM)]
    monkeypatch.setattr(pipeline.trends, "fetch", lambda token, kws, on_cost=None: tr_rows)
    monkeypatch.setattr(pipeline.O, "briefs", lambda items, key: ({0: {"i": 0, "name": "طرح آزمایشی", "brief": "ب"}}, 0.002))
    out = pipeline.run("t1")
    html = out.read_text(encoding="utf-8")
    assert "گزارش ترند" in html and "نکته‌ی آزمایشی" in html
    assert "لیست آزمایش این هفته" in html and "طرح آزمایشی" in html
    assert (tmp_path / "runs" / "t1" / "opportunities.csv").exists()
    assert "۴۰ پرفروش اول دیجی‌کالا" in html and "همین طرح در ۲۰ پرفروش دیجی‌کالا" in html
    assert "گوگل ترندز ایران" in html
    opps = json.loads((tmp_path / "runs" / "t1" / "opportunities.json").read_text(encoding="utf-8"))
    assert any(o["source"] == "google" and o["q"] == "گردنبند اسم انگلیسی" for o in opps)
    assert (tmp_path / "runs" / "t1" / "products.csv").exists()
    pipeline.run("t1")                         # resume: no new AI calls
    assert calls["n"] == 2          # Etsy+Basalam once, Digikala once; resume adds none
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


def test_digikala_card():
    c = digikala.card(DK_PRODUCT, "گردنبند", 3)
    assert c["price_toman"] == 699000 and c["rating"] == 4.06 and c["reviews"] == 555
    assert c["url"].startswith("https://www.digikala.com/product/dkp-18411251") and c["image"].endswith("a.jpg")
    out = digikala.card({**DK_PRODUCT, "default_variant": []}, "q", 1)
    assert out["available"] is False and out["price_toman"] is None


def test_trends_row_and_ideas():
    r = trends.row(TR_ITEM)
    assert r["peak_months"] == [12, 2] and r["next_peak"] == "2026-12-15" and r["yoy"] == 22.5
    assert r["rising"][0] == {"query": "گردنبند اسم انگلیسی", "value": "+250%"}
    ideas = trends.new_ideas([r], known={"گردنبند"})
    assert ideas == ["گردنبند اسم انگلیسی"]          # non-jewelry «قیمت دلار» left out, no duplicates
    assert "گردنبند اسم" in trends.keywords([{"q": "دستبند پاپیون"}]) and "دستبند پاپیون" in trends.keywords(
        [{"q": "دستبند پاپیون"}])


def test_jalali():
    from dastsaz.report import jalali
    assert jalali("2026-11-01") == "۱۰ آبان ۱۴۰۵" and jalali("2026-03-21") == "۱ فروردین ۱۴۰۵"
    assert jalali("2026-12-15") == "۲۴ آذر ۱۴۰۵" and jalali("") == ""


def test_digikala_match_counts_only_same_design(monkeypatch):
    from dastsaz import opportunities as O
    cards = [digikala.card({**DK_PRODUCT, "id": i, "title_fa": t}, "q", i) for i, t in
             enumerate(["دستبند زنانه طرح پاپیون", "دستبند\u200cپاپیون نقره", "گردنبند پاپیون", "دستبند قلب"])]
    monkeypatch.setattr(O.digikala, "search", lambda q, session=None, sleep=None: (cards, 900))
    o = {"q": "دستبند پاپیون", "week": 9, "supply": 100, "momentum": 0.01, "source": "basalam", "score": 1}
    O.add_digikala([o], session=object())
    assert o["dk_match"] == 2 and o["dk_reviews"] == 1110


def test_trends_month_names_and_filters():
    import datetime as dt
    it = {"keyword": "گردنبند", "averageInterest": 63.9, "seasonality": {"isSeasonal": False, "peakMonths": ["Aug", "Jul"],
          "monthlyProfile": {"Jan": 59.7, "Aug": 72.5, "Jul": 69.5}, "nextPeakDate": None}}
    r = trends.row(it)
    assert r["peak_months"] == [8, 7] and r["next_peak"].endswith("-08-15") and r["order_by"].endswith("-07-18")
    assert trends.next_peak({"Aug": 72, "Jan": 3}, dt.date(2026, 11, 1)) == ("2027-08-15", "2027-07-18")
    rows = [{"breakout": [{"query": q, "value": ""} for q in [
        "گوشواره ونکلیف", "تعبیر خواب گوشواره طلا", "گوشواره ایرپاد", "لیست قیمت گوشواره طلا",
        "کاپشن صورتی گوشواره قلبی", "گوشواره قلبی"]], "rising": []}]
    assert trends.new_ideas(rows, set()) == ["گوشواره قلبی"]
    from dastsaz import opportunities as O
    o = {"q": "گوشواره ونکلیف", "type": "گوشواره", "term": "x", "labels": ["در حال اوج"], "week": 20, "score": 9}
    assert O.pick([o]) == []
