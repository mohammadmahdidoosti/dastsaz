"""Google Trends for Iran (geo IR) through Apify (actor kwerix/google-trends-api; Google's own Trends API is still a
closed alpha and pytrends was archived). Per keyword: yearly direction, seasonality (peak months, next peak date)
and rising / breakout searches. About $0.0015 per keyword.

Used for: timing (order from the maker weeks before the peak: Yalda, mother's day, Sepandarmazgan, Nowruz)
and new ideas (rising searches become extra Basalam/Digikala opportunity searches).
"""
from __future__ import annotations

import datetime as dt
import logging
import re

from . import config as C
from .etsy import Apify

log = logging.getLogger(__name__)
ACTOR = "kwerix~google-trends-api"
BASE = ["گردنبند", "گوشواره", "دستبند", "انگشتر", "پابند", "زیورآلات", "گردنبند اسم", "گردنبند نقره",
        "دستبند نقره", "انگشتر نقره", "گوشواره نقره", "ست عروس", "زیورآلات دست ساز", "گردنبند طلا",
        "دستبند طلا", "آویز", "سنگ فیروزه", "انگشتر فیروزه"]
JEWELRY = re.compile(r"گردن|گوشوار|دستبند|انگشتر|پابند|آویز|زیور|جواهر|نقره|طلا|سنگ|مروارید|ست|النگو|سنجاق|بدلیجات")
MONTHS_FA = {1: "ژانویه (دی/بهمن)", 2: "فوریه (بهمن/اسفند)", 3: "مارس (اسفند/فروردین)", 4: "آوریل (فروردین/اردیبهشت)",
             5: "مه (اردیبهشت/خرداد)", 6: "ژوئن (خرداد/تیر)", 7: "ژوئیه (تیر/مرداد)", 8: "اوت (مرداد/شهریور)",
             9: "سپتامبر (شهریور/مهر)", 10: "اکتبر (مهر/آبان)", 11: "نوامبر (آبان/آذر)", 12: "دسامبر (آذر/دی)"}


MON = {m: i for i, m in enumerate(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}
# rising searches that are not a design to make: questions, prices, dreams, memes, earbuds, and brand names
# (copying a brand's design is a legal risk, so brands never become test-list ideas)
NOT_DESIGN = re.compile(r"تعبیر|خواب|قیمت|لیست|خرید|فروش|آموزش|چطور|چگونه|ایرپاد|ایربادز|هندزفری|کاپشن|دختر|پسر|"
                        r"عکس|فیلم|آهنگ|سریال|بازیگر|طلا فروشی|گرم|عیار|نرخ|بورس|مدل جدید ۱۴|سکه")
BRANDS = re.compile(r"ونکلیف|ون کلیف|تیفانی|ورساچه|کارتیه|گوچی|شنل|دیور|پاندورا|سواروسکی|بولگاری|لویی|هرمس|"
                    r"van ?cleef|tiffany|versace|cartier|gucci|chanel|dior|pandora|swarovski|bvlgari", re.I)


def _month(m) -> int | None:
    if isinstance(m, int) or str(m).isdigit():
        return int(m)
    return MON.get(str(m)[:3].title())


def next_peak(profile: dict, today: dt.date | None = None) -> tuple[str, str]:
    """From the average interest per month: the next 15th of the strongest month, and 4 weeks before it."""
    if not profile:
        return "", ""
    best = max(profile.items(), key=lambda kv: kv[1] or 0)[0]
    m = _month(best)
    if not m:
        return "", ""
    today = today or dt.date.today()
    y = today.year if (m, 15) > (today.month, today.day) else today.year + 1
    peak = dt.date(y, m, 15)
    return peak.isoformat(), (peak - dt.timedelta(days=28)).isoformat()


def keywords(test_list: list[dict] | None = None, extra: int = 12) -> list[str]:
    out = list(BASE)
    for o in (test_list or [])[:extra]:
        if o.get("q") and o["q"] not in out:
            out.append(o["q"])
    return out


def _queries(v) -> list[dict]:
    """The actor's related-query lists may hold strings or dicts; keep {query, value}."""
    out = []
    for x in v or []:
        if isinstance(x, str):
            out.append({"query": x, "value": ""})
        elif isinstance(x, dict):
            q = x.get("query") or x.get("title") or x.get("keyword") or ""
            val = x.get("formattedValue") or x.get("value") or x.get("growth") or ""
            if q:
                out.append({"query": str(q), "value": str(val)})
    return out


def row(it: dict) -> dict:
    s = it.get("seasonality") or {}
    prof = s.get("monthlyProfile") or it.get("monthlyProfile") or {}
    nxt, order = s.get("nextPeakDate") or "", s.get("publishBy") or ""
    if not nxt and prof:
        nxt, order = next_peak(prof)
    return {
        "keyword": it.get("keyword") or "", "average": it.get("averageInterest"), "latest": it.get("latestInterest"),
        "yoy": it.get("yoyChangePct"), "slope": it.get("trendSlopePctPerYear"),
        "seasonal": bool(s.get("isSeasonal")), "season_index": s.get("seasonalityIndex"),
        "peak_months": [m for m in (_month(x) for x in (s.get("peakMonths") or [])) if m],
        "next_peak": nxt, "order_by": order,
        "rising": _queries(it.get("risingQueries")), "breakout": _queries(it.get("breakoutQueries")),
        "top": _queries(it.get("topQueries"))[:10], "low_precision": bool(it.get("lowPrecision")),
        "url": it.get("trendsUrl") or "",
    }


def fetch(token: str, kws: list[str], on_cost=None) -> list[dict]:
    ap = Apify(token)
    inp = {"keywords": kws, "geo": "IR", "timeRange": "today 5-y", "includeRelatedQueries": True}
    run = ap.run(inp, C.TRENDS_MAX_USD, actor=ACTOR)
    if on_cost:
        on_cost(len(kws), ap.cost(run), run.get("status"))
    items = ap.items(run["defaultDatasetId"]) if run.get("defaultDatasetId") else []
    return [row(it) for it in items if isinstance(it, dict) and it.get("keyword")]


def new_ideas(rows: list[dict], known: set[str], n: int = 12) -> list[str]:
    """Breakout and rising searches about jewelry that we don't search yet: extra opportunity searches."""
    out = []
    for r in rows:
        for q in r["breakout"] + r["rising"]:
            t = q["query"].strip()
            if (t and t not in known and t not in out and JEWELRY.search(t) and len(t) <= 30
                    and len(t.split()) <= 4 and not NOT_DESIGN.search(t) and not BRANDS.search(t)):
                out.append(t)
    return out[:n]
