"""Google Trends for Iran (geo IR) through Apify (actor kwerix/google-trends-api; Google's own Trends API is still a
closed alpha and pytrends was archived). Per keyword: yearly direction, seasonality (peak months, next peak date)
and rising / breakout searches. About $0.0015 per keyword.

Used for: timing (order from the maker weeks before the peak: Yalda, mother's day, Sepandarmazgan, Nowruz)
and new ideas (rising searches become extra Basalam/Digikala opportunity searches).
"""
from __future__ import annotations

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
    return {
        "keyword": it.get("keyword") or "", "average": it.get("averageInterest"), "latest": it.get("latestInterest"),
        "yoy": it.get("yoyChangePct"), "slope": it.get("trendSlopePctPerYear"),
        "seasonal": bool(s.get("isSeasonal")), "peak_months": [int(m) for m in (s.get("peakMonths") or [])
                                                                if str(m).isdigit()],
        "next_peak": s.get("nextPeakDate") or "", "order_by": s.get("publishBy") or "",
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
            if t and t not in known and t not in out and JEWELRY.search(t) and len(t) <= 40:
                out.append(t)
    return out[:n]
