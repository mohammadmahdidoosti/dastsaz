import datetime as dt
import json
import random

import pytest

from dastsaz import analyze as A
from dastsaz import basalam, config as C, digikala, etsy, guard, pipeline, trends


BAS_PRODUCT = {"id": 39072910, "name": "گردنبند نقره اسم دلخواه", "price": 1200000, "primaryPrice": 1500000,
               "rating": {"average": 4.8, "count": 6}, "sales_count": 80, "sales_count_week": 7,
               "categoryTitle": "گردنبند", "photo": {"MEDIUM": "https://statics.basalam.com/x.jpg"},
               "vendor": {"name": "نقره‌کاری", "identifier": "noghrekari", "owner": {"city": "اصفهان"}}}

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
    from dastsaz import analysis
    monkeypatch.setattr(analysis, "executive", lambda st, tl, tr, mk, key, extra=None: (
        {"headline": "تیتر آزمایشی", "findings": [{"title": "یافته", "text": "نکته‌ی آزمایشی"}],
         "actions": ["کار اول"], "risks": ["ریسک"], "maker_brief": "متن سازنده"}, 0.001))

    def fake_search(q, size=30, session=None, sleep=None):
        return [basalam.card({**BAS_PRODUCT, "id": hash(q) % 1000 + i, "sales_count_week": 5, "name": q + " نقره"}, q, i)
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
    monkeypatch.setattr(pipeline.suggest, "fetch", lambda progress=None: {
        "counts": {"گردنبند ماه و ستاره": 6, "گردنبند": 9, "قیمت گردنبند": 3}, "trending": ["گوشی"]})
    monkeypatch.setattr(pipeline.reviews, "collect", lambda tl, progress=None: {"x": [{"star": 2, "text": "زود سیاه شد"}]})
    monkeypatch.setattr(pipeline.reviews, "summarize", lambda tl, raw, key: (
        {o["q"]: {"n": 4, "low": 1, "avg": 4.2, "complaints": ["زود سیاه شد"], "improve": "آبکاری ضخیم‌تر"} for o in tl}, 0.001))
    monkeypatch.setattr(pipeline.makers, "details", lambda top, progress=None: [
        {**sh, "city": "اصفهان", "province": "اصفهان", "types": [], "since": "2021", "catalog": 30, "maker": True,
         "url": "https://basalam.com/x"} for sh in top])
    monkeypatch.setattr(pipeline.metals, "fetch", lambda: {
        "silver_925": {"name": "نقره ۹۲۵ (هر گرم)", "toman": 434634, "time": ""}})
    out = pipeline.run("t1")
    html = out.read_text(encoding="utf-8")
    assert "مناسبت‌ها و قیمت فلز" in html and "۴۳۵ هزار تومان" in html
    assert "سازنده‌های احتمالی" in html and "اصفهان" in html
    assert "مردم چه تایپ می‌کنند" in html and "گردنبند ماه و ستاره" in html
    assert "زود سیاه شد" in html and "آبکاری ضخیم‌تر" in html
    assert "گزارش ترند" in html and "نکته‌ی آزمایشی" in html and "تیتر آزمایشی" in html and "متن سازنده" in html
    assert "خرید از سازنده" in html and "نقشه‌ی فرصت‌ها" in html and "سه بازار، سه مشتری" in html
    assert "لیست آزمایش این هفته" in html and "طرح آزمایشی" in html
    assert (tmp_path / "runs" / "t1" / "opportunities.csv").exists()
    assert "۴۰ پرفروش اول دیجی‌کالا" in html and "همین طرح در دیجی‌کالا" in html
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


def test_executive_asks_without_reasoning(monkeypatch):
    from dastsaz import analysis, report
    sent = {}

    def fake_post(url, json=None, timeout=None, headers=None):
        sent.update(json)
        return FakeResp({"choices": [{"message": {"content": '{"headline": "ت", "findings": [{"title": "a", "text": "b"}],'
                                                             ' "actions": ["x"], "risks": [], "maker_brief": "m"}'}}],
                         "usage": {"cost": 0.002}})
    monkeypatch.setattr(analysis.requests, "post", fake_post)
    ex, usd = analysis.executive(report.stats([], []), [], [], [], "k")
    assert ex["headline"] == "ت" and ex["findings"][0]["text"] == "b" and usd == 0.002
    assert sent["reasoning"] == {"enabled": False} and "عددی از خودت نساز" in sent["messages"][0]["content"]
    assert "هرگز در آن ننویس" in sent["messages"][0]["content"]


def test_economics_rules():
    from dastsaz import analysis
    o = {"week": 80, "supply": 162, "price_low": 65000, "price_high": 196000, "price_median": 120000,
         "dk_reviews": 0, "dk_match": 0, "source": "basalam", "weak": []}
    e = analysis.economics(o, 5)
    assert e["retail"] == 120000 and e["buy_max"] == 50000 and e["test_qty"] == 20 and e["channels"] == ["باسلام"]
    wide = analysis.economics({**o, "week": 3, "price_high": 1500000, "source": "etsy"}, 5)
    assert wide["test_qty"] == 6 and "اینستاگرام و سایت خودتان" in wide["channels"] and len(wide["risks"]) == 2

def test_seeds_and_signals():
    from dastsaz import opportunities as O
    bas = [{"motif": "طرح پاپیون", "sales_week": 9, "style": "فانتزی و بامزه", "material": "استیل"},
           {"motif": "پاپیون", "sales_week": 4, "style": "مینیمال", "material": "استیل"},
           {"motif": "بدون طرح", "sales_week": 50, "style": "مینیمال", "material": "استیل"}]
    ets = [{"motif": "گل", "style": "وینتیج", "material": "روکش طلا"} for _ in range(5)]
    sd = O.seeds(ets, bas)
    terms = [x["term"] for x in sd]
    assert terms[0] == "پاپیون" and "بدون طرح" not in terms and "وینتیج" in terms and "گل" in terms
    cards = [basalam.card({**BAS_PRODUCT, "id": i, "sales_count_week": 3, "sales_count": 20, "name": "گوشواره پاپیون"},
                          "q", i) for i in range(10)]
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


def test_relevance_drops_unrelated_results():
    from dastsaz import opportunities as O
    cards = [basalam.card({**BAS_PRODUCT, "id": i, "name": n}, "q", i) for i, n in
             enumerate(["گردنبند دم وال نقره", "گردنبند استیل دم وال", "گردنبند\u200cدم وال", "گردنبند قلب"])]
    o = O.signals({"q": "گردنبند دم وال", "type": "گردنبند", "term": "دم وال", "why": "", "source": "google"}, cards, 50)
    assert o["match"] == 3
    lyric = O.signals({"q": "بگو هنوزم داری گردنبند", "type": "گردنبند", "term": "x", "why": "", "source": "google"},
                      cards, 50)
    assert lyric["match"] == 0 and O.pick([dict(lyric, labels=["در حال اوج"], week=50)]) == []


def test_ai_text_gets_persian_digits():
    from dastsaz.page import P
    assert P("16.5 درصد و 60,000 تومان <b>") == "۱۶٫۵ درصد و ۶۰٬۰۰۰ تومان &lt;b&gt;"


def test_occasions_dates_and_matching():
    import datetime as dt
    from dastsaz import occasions
    tl = [{"q": "گردنبند اسم مادر"}, {"q": "دستبند ست"}, {"q": "دستبند ساده"}]
    occ = occasions.upcoming(dt.date(2026, 11, 1), days=60, test_list=tl)
    names = {o["name"]: o for o in occ}
    mom = next(o for n, o in names.items() if "مادر" in n)
    assert mom["date"] == "2026-11-30" and mom["days_left"] == 29
    yalda = next(o for n, o in names.items() if "یلدا" in n)
    assert yalda["date"] == "2026-12-21"
    assert occasions.j2g(1405, 10, 1) == dt.date(2026, 12, 22)


def test_metal_note_and_suggest_ideas():
    from dastsaz import metals, suggest
    pr = {"silver_925": {"name": "n", "toman": 430000, "time": ""}}
    assert "ممکن نیست" in metals.silver_note({"q": "گردنبند نقره"}, 900000, pr)
    assert metals.silver_note({"q": "گردنبند استیل"}, 900000, pr) == ""
    ids = suggest.ideas({"counts": {"گردنبند": 9, "گردنبند ماه و ستاره": 5, "قیمت گردنبند طلا": 4}}, set())
    assert "گردنبند ماه و ستاره" in ids and "گردنبند" not in ids


def test_maker_flag(monkeypatch):
    from dastsaz import makers

    class R:
        def __init__(self, d): self.d = d
        def json(self): return self.d

    class S:
        def get(self, url, timeout=20):
            if "a1" in url:
                return R({"title": "کارگاه نقره", "description": "ساخت دست خودم", "city": {"title": "زنجان",
                          "parent": {"title": "زنجان"}}, "created_at": "2020-01-01"})
            return R({"title": "پخش عمده", "description": "اجناس وارداتی چین"})
    monkeypatch.setattr(makers.basalam, "_session", lambda: S())
    top = makers.shops([{"shop_id": "a1", "shop": "a", "sales_total": 5, "sales_week": 1},
                        {"shop_id": "b2", "shop": "b", "sales_total": 50, "sales_week": 3}])
    out = makers.details(top, sleep=lambda s: None)
    assert out[0]["id"] == "a1" and out[0]["maker"] and out[0]["province"] == "زنجان"
    assert not out[1]["maker"]


def test_backtest_beats_flat_on_seasonal_data():
    import math
    from dastsaz import backtest as B, page
    months = B._months("2021-01", "2025-12")
    rnd = random.Random(3)
    series = {f"k{i}": [50 + 30 * math.sin(2 * math.pi * (j + i) / 12) + rnd.uniform(-3, 3) for j in range(len(months))]
              for i in range(12)}
    sc = B.evaluate(series, months)
    assert sc["ours"]["direction"] > sc["persist"]["direction"] + 0.2
    assert sc["ours"]["pick_hit"] > sc["_base"]["up"]
    ex = B.last_cutoff(series, months)
    html = page.backtest_page([{"source": "trends", "months": [months[0], months[-1]], "keywords": 12,
                                "scores": sc, "example": ex, "usd": 0.01}])
    assert "روش گزارش" in html and "جهت درست" in html


def test_trends_monthly_drops_partial():
    from dastsaz import backtest as B
    m = B.monthly([{"date": "2025-01-05", "value": 10}, {"date": "2025-01-12", "value": 20},
                   {"date": "2025-02-02", "value": 99, "isPartial": True}])
    assert m == {"2025-01": 15.0}


def test_signal_scores_a_page_that_leads_sales(tmp_path, monkeypatch):
    from dastsaz import backtest as B, signals as S
    monkeypatch.setattr(C, "DATA_DIR", tmp_path)
    (tmp_path / "backtest").mkdir()
    months = B._months("2025-01", "2026-10")
    designs = [f"گردنبند طرح{i}" for i in range(10)]
    prods, des = {}, {}
    for i, q in enumerate(designs):
        dates = []
        for j, mo in enumerate(months):
            n = 3 + (6 if (i < 3 and mo >= "2026-02") else 0)        # designs 0-2 take off in Feb 2026
            dates += [mo + "-10"] * n
        prods[str(i)] = dates
        des[q] = [str(i)]
    (tmp_path / "backtest" / "reviews_raw_jewelry.json").write_text(
        json.dumps({"products": prods, "designs": des}, ensure_ascii=False), encoding="utf-8")
    posts = [{"ownerUsername": "lead", "timestamp": f"2025-{m:02d}-05T10:00:00", "caption": f"طرح{i} جدید",
              "likesCount": 500, "commentsCount": 10} for m in (10, 11, 12) for i in range(3)]
    posts += [{"ownerUsername": "noise", "timestamp": f"2025-{m:02d}-05T10:00:00", "caption": f"طرح{i}",
               "likesCount": 500, "commentsCount": 10} for m in (10, 11, 12) for i in (5, 6, 7)]
    (tmp_path / "ig_posts.json").write_text(json.dumps(posts, ensure_ascii=False), encoding="utf-8")
    (tmp_path / "ig_pages.json").write_text(json.dumps([{"username": "lead", "followersCount": 10000},
                                                        {"username": "noise", "followersCount": 10000}]), encoding="utf-8")
    r = S.evaluate_all()
    assert r["sources"]["پیج lead"]["lift"] > r["sources"]["پیج noise"]["lift"]
    assert r["sources"]["پیج lead"]["hit"] == 1.0
