"""How right is the recommender? Test it on the past.

We go back in time to a cutoff month, let each method predict from the data up to that month only, then compare
with what really happened in the next 3 months. Done at many cutoffs, so luck evens out.

Methods compared (each predicts growth of the next 3 months against the last 3 months):
- «ثابت» (persistence): nothing changes. The simplest guess; a useful system must beat it.
- «روند اخیر» (momentum): the last 3 months keep their direction.
- «پارسال همین موقع» (seasonal naive): the same change as the same months last year.
- «روش گزارش» (ours): average seasonal change over all earlier years, plus the yearly trend.
  This is what the report's Google section uses (peak months + year-over-year direction).

Data:
- trends: Google Trends Iran, 5 years weekly -> monthly (Apify kwerix, ~$0.003 per keyword).
- reviews: Basalam buyer reviews with dates -> monthly review counts per design, a stand-in for monthly sales
  (free, read slowly).

Run on the server:  python -m dastsaz.backtest trends   |   python -m dastsaz.backtest reviews
Result page: /backtest
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import random
import sys
import time
from collections import defaultdict
from pathlib import Path

from . import config as C

log = logging.getLogger(__name__)
H = 3                       # months ahead
BAND = 0.10                 # a change smaller than 10% counts as «ثابت»
TOP = 5                     # picks per cutoff
TREND_ACTOR = "kwerix~google-trends-api"
TREND_KWS = ["گردنبند", "گوشواره", "دستبند", "انگشتر", "پابند", "زیورآلات", "گردنبند اسم", "گردنبند نقره",
             "دستبند نقره", "انگشتر نقره", "گوشواره نقره", "ست عروس", "زیورآلات دست ساز", "گردنبند طلا",
             "دستبند طلا", "آویز", "انگشتر فیروزه", "گردنبند مروارید", "دستبند چرم", "گوشواره حلقه ای",
             "گردنبند پروانه", "گردنبند قلب", "دستبند مهره", "انگشتر مردانه", "دستبند مردانه", "گردنبند حرف",
             "گردنبند ماه", "زنجیر", "گوشواره آویز", "بدلیجات"]
KITCHEN_KWS = ["قابلمه", "ماهیتابه", "سرویس قابلمه", "زودپز", "کتری", "چای ساز", "قهوه ساز", "سرخ کن بدون روغن",
               "آبمیوه گیری", "مخلوط کن", "غذاساز", "همزن", "توستر", "اسپرسو ساز", "سماور", "قوری", "فلاسک",
               "ظرف غذا", "تابه گریل", "کارد", "تخته گوشت", "ادویه دان", "سرویس چاقو", "کاسه", "لیوان"]
KITCHEN_QUERIES = ["قابلمه گرانیتی", "ماهیتابه سنگی", "تابه گریل", "سرویس قابلمه", "کتری استیل", "قوری چینی",
                   "قوری مسی", "ادویه دان", "تخته گوشت چوبی", "ظرف سفالی", "کاسه سفالی", "لیوان سرامیکی",
                   "دیزی سنگی", "سماور ذغالی", "سرویس چاقو", "جاقاشقی", "ظرف درب دار", "سینی چوبی",
                   "قندان", "رومیزی"]
CATS = {"jewelry": "جواهر", "kitchen": "لوازم آشپزخانه (دسته‌ی کنترل)"}
METHODS = {"persist": "ثابت (هیچ تغییری نمی‌کند)", "momentum": "روند اخیر ادامه پیدا می‌کند",
           "seasonal": "پارسال همین موقع", "season_avg": "میانگین فصل در همه‌ی سال‌های قبل",
           "ours": "روش گزارش (فصل + روند سالانه)"}


def _dir() -> Path:
    d = C.DATA_DIR / "backtest"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def _ratio(a, b):
    return None if a is None or not b else a / b - 1


def _cls(g) -> int:
    return 0 if g is None or abs(g) < BAND else (1 if g > 0 else -1)


# ---------------------------------------------------------------- methods (only data up to t is used)
def predict(s: list[float], t: int, method: str):
    if t < 5:
        return None
    if method == "persist":
        return 0.0
    if method == "momentum":
        return _ratio(_mean(s[t - 2:t + 1]), _mean(s[t - 5:t - 2]))
    if method == "seasonal":
        if t < 14:
            return None
        return _ratio(_mean(s[t - 11:t - 8]), _mean(s[t - 14:t - 11]))
    if method in ("ours", "season_avg"):
        seas = [_ratio(_mean(s[t - 12 * k + 1:t - 12 * k + 4]), _mean(s[t - 12 * k - 2:t - 12 * k + 1]))
                for k in range(1, 6) if t - 12 * k - 2 >= 0]
        seas = [x for x in seas if x is not None]
        if not seas:
            return None
        if method == "season_avg":
            return _mean(seas)
        yoy = _ratio(_mean(s[t - 2:t + 1]), _mean(s[t - 14:t - 11])) if t >= 14 else 0.0
        yoy = max(-0.9, min(3.0, yoy or 0.0))
        return (1 + _mean(seas)) * (1 + yoy) ** (H / 12) - 1
    raise ValueError(method)


def actual(s: list[float], t: int):
    return _ratio(_mean(s[t + 1:t + 1 + H]), _mean(s[t - 2:t + 1]))


def evaluate(series: dict[str, list[float]], months: list[str], min_t: int = 14) -> dict:
    """series: name -> monthly values on the same months. Returns scores per method and per-cutoff picks."""
    n = len(months)
    score = {m: {"cases": 0, "dir_ok": 0, "abs_err": 0.0, "pick_hits": 0, "picks": 0, "pick_growth": 0.0}
             for m in METHODS}
    base = {"cases": 0, "up": 0, "growth": 0.0, "rand_hits": 0.0}
    for t in range(min_t, n - H):
        ys = {k: actual(s, t) for k, s in series.items()}
        ys = {k: y for k, y in ys.items() if y is not None}
        if len(ys) < TOP * 2:
            continue
        base["cases"] += len(ys)
        base["up"] += sum(1 for y in ys.values() if y > 0)
        base["growth"] += sum(ys.values())
        for m in METHODS:
            ps = {k: predict(series[k], t, m) for k in ys}
            ps = {k: p for k, p in ps.items() if p is not None}
            for k, p in ps.items():
                sc = score[m]
                sc["cases"] += 1
                sc["dir_ok"] += _cls(p) == _cls(ys[k])
                sc["abs_err"] += min(abs(p - ys[k]), 3.0)
            if m != "persist" and len(ps) >= TOP * 2:
                top = sorted(ps, key=lambda k: -ps[k])[:TOP]
                score[m]["picks"] += len(top)
                score[m]["pick_hits"] += sum(1 for k in top if ys[k] > 0)
                score[m]["pick_growth"] += sum(ys[k] for k in top)
    out = {}
    for m, sc in score.items():
        if not sc["cases"]:
            continue
        out[m] = {"name": METHODS[m], "cases": sc["cases"], "direction": sc["dir_ok"] / sc["cases"],
                  "error": sc["abs_err"] / sc["cases"],
                  "pick_hit": sc["pick_hits"] / sc["picks"] if sc["picks"] else None,
                  "pick_growth": sc["pick_growth"] / sc["picks"] if sc["picks"] else None}
    if base["cases"]:
        out["_base"] = {"up": base["up"] / base["cases"], "growth": base["growth"] / base["cases"],
                        "cases": base["cases"]}
    return out


def last_cutoff(series: dict[str, list[float]], months: list[str]) -> list[dict]:
    """The latest testable cutoff: what each method said then, and what happened."""
    t = len(months) - H - 1
    rows = []
    for k, s in series.items():
        y = actual(s, t)
        if y is None:
            continue
        rows.append({"name": k, "actual": y, **{m: predict(s, t, m) for m in ("momentum", "seasonal", "season_avg", "ours")}})
    rows.sort(key=lambda r: -(r["ours"] if r["ours"] is not None else -9))
    return [{"cutoff": months[t], "until": months[t + H]}] + rows


# ---------------------------------------------------------------- Google Trends
def monthly(points: list[dict]) -> dict[str, float]:
    m = defaultdict(list)
    for p in points or []:
        if p.get("isPartial") or p.get("value") is None:
            continue
        m[str(p.get("date"))[:7]].append(float(p["value"]))
    return {k: sum(v) / len(v) for k, v in sorted(m.items())}


def trends_series(items: list[dict]) -> tuple[dict[str, list[float]], list[str]]:
    per = {it["keyword"]: monthly(it.get("interestOverTime")) for it in items if it.get("keyword")}
    months = sorted({mo for d in per.values() for mo in d})
    if months:
        months = months[:-1] if len(months) > 13 else months        # the current month is not complete
    series = {}
    for k, d in per.items():
        s = [d.get(mo) for mo in months]
        vals = [x for x in s if x is not None]
        if len(vals) < len(months) * 0.9 or _mean(vals) < 3 or sum(1 for x in vals if x == 0) > len(vals) * 0.3:
            continue                                                   # too little search in Iran to judge
        series[k] = [x if x is not None else _mean(vals) for x in s]
    return series, months


def run_trends(token: str, cat: str = "jewelry") -> dict:
    from .etsy import Apify
    d = _dir()
    raw = d / ("trends_raw.json" if cat == "jewelry" else f"trends_raw_{cat}.json")
    kws = TREND_KWS if cat == "jewelry" else KITCHEN_KWS
    if raw.exists() and time.time() - raw.stat().st_mtime < 7 * 86400:
        items = json.loads(raw.read_text(encoding="utf-8"))
        usd = 0.0
    else:
        ap = Apify(token)
        run = ap.run({"keywords": kws, "geo": "IR", "timeRange": "today 5-y", "includeRelatedQueries": False,
                      "includeInterestOverTime": True}, 0.3, actor=TREND_ACTOR)
        items = ap.items(run["defaultDatasetId"]) if run.get("defaultDatasetId") else []
        usd = ap.cost(run)
        raw.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
    series, months = trends_series(items)
    res = {"source": "trends", "cat": cat, "when": dt.date.today().isoformat(), "usd": usd, "keywords": len(series),
           "skipped": [it.get("keyword") for it in items if it.get("keyword") not in series],
           "months": [months[0], months[-1]] if months else [], "scores": evaluate(series, months),
           "example": last_cutoff(series, months) if months else []}
    (d / f"trends_{cat}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    return res


# ---------------------------------------------------------------- Basalam reviews (monthly reviews ~ monthly sales)
REV_URL = "https://services.basalam.com/web/v1/review/product/{id}/reviews"


def product_reviews(s, pid, since: str, sleep=time.sleep, max_pages: int = 12) -> list[str]:
    """Review dates (YYYY-MM-DD), newest first, back to `since`."""
    out = []
    for page in range(max_pages):
        sleep(random.uniform(1.5, 3.5))
        try:
            j = s.get(REV_URL.format(id=pid), params={"limit": 50, "offset": page * 50}, timeout=20).json()
        except Exception as e:  # noqa: BLE001
            log.warning("reviews %s: %s", pid, e)
            break
        revs = j.get("reviews") or []
        dates = [str(r.get("createdAt") or "")[:10] for r in revs if r.get("createdAt")]
        out += dates
        if not j.get("has_next") or not dates or min(dates) < since:
            break
    return [x for x in out if x >= since]


DK_URL = "https://api.digikala.com/v1/product/{id}/comments/"
JMONTHS = ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور", "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"]
FA2EN = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")


def jdate(t: str) -> str:
    """'9 آبان 1405' -> '2026-10-31' ('' if unreadable)."""
    from .occasions import j2g
    parts = str(t or "").translate(FA2EN).split()
    try:
        d, m, y = int(parts[0]), JMONTHS.index(parts[1]) + 1, int(parts[2])
        return j2g(y, m, d).isoformat()
    except (ValueError, IndexError):
        return ""


def dk_reviews(s, pid, since: str, sleep=time.sleep, max_pages: int = 25) -> list[str]:
    out = []
    for page in range(1, max_pages + 1):
        sleep(random.uniform(2.0, 4.0))
        try:
            data = (s.get(DK_URL.format(id=pid), params={"page": page}, timeout=20).json() or {}).get("data") or {}
        except Exception as e:  # noqa: BLE001
            log.warning("dk reviews %s: %s", pid, e)
            break
        dates = [x for x in (jdate(c.get("created_at")) for c in data.get("comments") or []) if x]
        out += dates
        pager = data.get("pager") or {}
        if not dates or min(dates) < since or page >= int(pager.get("total_pages") or 0):
            break
    return [x for x in out if x >= since]


def run_reviews(queries: list[str] | None = None, n: int = 40, per: int = 8, progress=None,
                sleep=time.sleep, cat: str = "jewelry", market: str = "basalam") -> dict:
    from . import basalam, digikala
    d = _dir()
    tag = "" if market == "basalam" else "dk_"
    cache_f = d / f"reviews_raw_{tag}{cat}.json"
    cache = json.loads(cache_f.read_text(encoding="utf-8")) if cache_f.exists() else {"products": {}, "designs": {}}
    if queries is None:
        queries = latest_queries(n) if cat == "jewelry" else KITCHEN_QUERIES
    today = dt.date.today()
    since = (today.replace(day=1) - dt.timedelta(days=30 * 26)).isoformat()
    s = basalam._session() if market == "basalam" else digikala._session()
    for i, q in enumerate(queries):
        if q not in cache["designs"]:
            sleep(random.uniform(*C.BASALAM_DELAY))
            try:
                if market == "basalam":
                    cards, _ = basalam.search(q, size=per * 2, session=s, sleep=lambda *_: None)
                else:
                    cards, _ = digikala.search(q, session=s, sleep=lambda *_: None)
            except Exception as e:  # noqa: BLE001
                log.warning("search %s: %s", q, e)
                continue
            words = q.split()
            ids = [str(c["id"]) for c in cards if all(w in c.get("title", "") for w in words)][:per]
            cache["designs"][q] = ids
        for pid in cache["designs"][q]:
            if pid not in cache["products"]:
                cache["products"][pid] = (product_reviews(s, pid, since, sleep=sleep) if market == "basalam"
                                          else dk_reviews(s, pid, since, sleep=sleep))
        cache_f.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
        if progress:
            progress(i + 1, len(queries))
    months = _months(since[:7], (today.replace(day=1) - dt.timedelta(days=1)).isoformat()[:7])
    series = {}
    for q, ids in cache["designs"].items():
        if q not in queries:
            continue
        cnt = defaultdict(int)
        for pid in ids:
            for x in cache["products"].get(pid, []):
                cnt[x[:7]] += 1
        s_ = [float(cnt.get(mo, 0)) for mo in months]
        if sum(s_[-6:]) >= 6:                     # enough buyers recently to judge
            series[q] = s_
    res = {"source": "reviews" if market == "basalam" else "reviews_dk", "cat": cat, "when": today.isoformat(), "usd": 0.0, "keywords": len(series),
           "designs": len(cache["designs"]), "months": [months[0], months[-1]] if months else [],
           "scores": evaluate(series, months), "example": last_cutoff(series, months) if months else []}
    (d / f"reviews_{tag}{cat}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    return res


def _months(a: str, b: str) -> list[str]:
    y, m = map(int, a.split("-"))
    out = []
    while f"{y:04d}-{m:02d}" <= b:
        out.append(f"{y:04d}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def latest_queries(n: int) -> list[str]:
    runs = sorted((C.DATA_DIR / "runs").glob("*/opportunities.json"), key=lambda p: p.stat().st_mtime)
    if not runs:
        return []
    opps = json.loads(runs[-1].read_text(encoding="utf-8"))
    opps = [o for o in opps if (o.get("match") or 0) >= 3]
    return [o["q"] for o in sorted(opps, key=lambda o: -(o.get("alltime") or 0))[:n]]


# ---------------------------------------------------------------- page
def results() -> list[dict]:
    d = C.DATA_DIR / "backtest"
    names = [f"{s}_{c}.json" for s in ("trends", "reviews", "reviews_dk") for c in CATS]
    return [json.loads((d / f).read_text(encoding="utf-8")) for f in names if (d / f).exists()]


def main(argv: list[str]) -> None:
    logging.basicConfig(level=logging.INFO)
    what = argv[1] if len(argv) > 1 else "trends"
    cat = argv[2] if len(argv) > 2 else "jewelry"
    if what == "trends":
        r = run_trends(C.secret("APIFY_TOKEN"), cat)
    elif what == "page":
        r = {"scores": {}}
    else:
        r = run_reviews(progress=lambda i, t: print(f"{i}/{t}", flush=True), cat=cat,
                        market="digikala" if what == "reviews_dk" else "basalam")
    for m, v in r["scores"].items():
        print(m, {k: (round(x, 3) if isinstance(x, float) else x) for k, x in v.items()})
    from .page import backtest_page
    (_dir() / "report.html").write_text(backtest_page(results()), encoding="utf-8")
    print("page: /backtest")


if __name__ == "__main__":
    main(sys.argv)
