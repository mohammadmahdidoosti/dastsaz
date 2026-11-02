"""The category radar: which whole categories are growing in Iran, so we hunt where the market gets bigger.

Base list: Etsy's full category tree (dastsaz/etsy_categories.txt, ~3000 names). Once, AI turns each into the Persian
words Iranians search on Basalam/Digikala and says whether a small Iranian maker could make or source it.
Every week, per category (one slow search each, free): Basalam weekly sales of the top matching products, number of
competing products, Digikala total; week-over-week change and life stage. Monthly (optional, ~$0.3): Google Trends
Iran 5 years -> season and long-run direction, and the same accuracy test at category level.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import random
import time
from pathlib import Path

from . import ai, basalam, digikala
from . import config as C
from .opportunities import _plain

log = logging.getLogger(__name__)
TOP = ["Accessories", "Art & Collectibles", "Bags & Purses", "Bath & Beauty", "Books, Films & Music", "Clothing",
       "Craft Supplies & Tools", "Electronics & Accessories", "Home & Living", "Jewellery", "Paper & Party Supplies",
       "Pet Supplies", "Shoes", "Toys & Games", "Weddings"]
RAW = Path(__file__).resolve().parent / "etsy_categories.txt"

ASK = """این‌ها دسته‌های محصول در Etsy است (top = دسته‌ی اصلی). برای هر کدام، به فارسی:
- fa: همان عبارتی که یک ایرانی برای خرید این محصول در باسلام یا دیجی‌کالا جست‌وجو می‌کند (۱ تا ۳ کلمه، رایج، بدون برند)
- fit: ۲ اگر یک سازنده‌ی کوچک یا کارگاه خانگی ایرانی می‌تواند بسازدش یا با سرمایه‌ی کم تأمینش کند و برای فروش آنلاین در ایران مناسب است؛
  ۱ اگر ممکن ولی سخت است؛ ۰ اگر نامناسب است (ماشین‌آلات بزرگ، خوراکی فاسدشدنی، دارو، محصول بزرگسالان، چیزی که در ایران رایج نیست، مبلمان بزرگ، دیجیتال)
فقط JSON: {"items": [{"i": 0, "fa": "", "fit": 0}]}"""


def _dir():
    d = C.DATA_DIR / "radar"
    d.mkdir(parents=True, exist_ok=True)
    return d


def etsy_list(raw: str | None = None) -> list[dict]:
    """Flat file -> [{'top', 'name'}], de-duplicated per top category."""
    lines = [x.strip() for x in (raw if raw is not None else RAW.read_text(encoding="utf-8")).splitlines() if x.strip()]
    out, top, k, seen = [], None, 0, set()
    for x in lines:
        if k < len(TOP) and x == TOP[k]:
            top, k = x, k + 1
            continue
        if top and (top, x) not in seen:
            seen.add((top, x))
            out.append({"top": top, "name": x})
    return out


def build(key: str, items: list[dict] | None = None, chunk: int = 120) -> list[dict]:
    """Translate + judge once; saved to /data/radar/categories.json (de-duplicated by Persian term)."""
    items = items if items is not None else etsy_list()
    out = []
    for k in range(0, len(items), chunk):
        part = items[k:k + chunk]
        res, _ = ai.ask_json(ASK, [{"i": j, "top": x["top"], "name": x["name"]} for j, x in enumerate(part)], key,
                             max_tokens=8000)
        by = {int(r.get("i", -1)): r for r in res.get("items") or []}
        for j, x in enumerate(part):
            r = by.get(j) or {}
            fa = str(r.get("fa") or "").strip()
            if fa:
                out.append({**x, "fa": fa, "fit": int(r.get("fit") or 0)})
    best: dict[str, dict] = {}
    for x in out:
        key_ = _plain(x["fa"])
        if key_ not in best or x["fit"] > best[key_]["fit"]:
            best[key_] = x
    cats = sorted(best.values(), key=lambda x: (-x["fit"], x["top"], x["fa"]))
    (_dir() / "categories.json").write_text(json.dumps(cats, ensure_ascii=False, indent=1), encoding="utf-8")
    return cats


def categories(min_fit: int = 1) -> list[dict]:
    f = _dir() / "categories.json"
    cats = json.loads(f.read_text(encoding="utf-8")) if f.exists() else []
    return [c for c in cats if c.get("fit", 0) >= min_fit]


def measure(cats: list[dict], progress=None, sleep=time.sleep) -> dict:
    """One slow Basalam search (+ one Digikala) per category."""
    sb, sd = basalam._session(), digikala._session()
    snap = {"date": dt.date.today().isoformat(), "cats": {}}
    for i, c in enumerate(cats):
        q = c["fa"]
        row = {"top": c["top"], "name": c["name"], "fit": c["fit"]}
        try:
            cards, total = basalam.search(q, size=20, session=sb, sleep=sleep)
            words = [w for w in _plain(q).split() if len(w) > 1]
            match = [x for x in cards if all(w in _plain(x.get("title")) for w in words)][:15]
            row.update({"supply": total, "match": len(match), "week": sum(x["sales_week"] for x in match),
                        "alltime": sum(x["sales_total"] for x in match),
                        "price": sorted(x["price_toman"] for x in match if x.get("price_toman"))[len(match) // 2]
                        if match else None})
        except RuntimeError:
            raise
        except Exception as e:  # noqa: BLE001
            log.warning("radar basalam %s: %s", q, e)
        if C.DIGIKALA:
            try:
                dcards, dtotal = digikala.search(q, session=sd, sleep=lambda *_: time.sleep(random.uniform(1, 2)))
                row.update({"dk_total": dtotal, "dk_reviews": sum(x.get("reviews") or 0 for x in dcards[:10])})
            except Exception as e:  # noqa: BLE001
                log.warning("radar digikala %s: %s", q, e)
        snap["cats"][q] = row
        if progress:
            progress(i + 1, len(cats))
    (_dir() / f"{snap['date']}.json").write_text(json.dumps(snap, ensure_ascii=False), encoding="utf-8")
    return snap


def history() -> list[dict]:
    return [json.loads(f.read_text(encoding="utf-8")) for f in sorted(_dir().glob("20*.json"))]


def board(hist: list[dict] | None = None) -> list[dict]:
    """Latest week per category, with demand per competitor, week-over-week change and life stage."""
    from .snapshot import stage
    hist = hist if hist is not None else history()
    if not hist:
        return []
    cur, prev = hist[-1]["cats"], (hist[-2]["cats"] if len(hist) > 1 else {})
    rows = []
    for q, r in cur.items():
        if r.get("week") is None:
            continue
        p = prev.get(q) or {}
        ch = (r["week"] - p["week"]) / p["week"] if p.get("week") else None
        sup = (r["supply"] - p["supply"]) / p["supply"] if p.get("supply") else 0.0
        rows.append({"q": q, **r, "per_seller": r["week"] / max(r.get("match") or 1, 1),
                     "gap": r["week"] / max(r.get("supply") or 1, 1) * 1000,
                     "change": ch, "stage": stage(ch, sup, r.get("supply") or 0) if p else "اولین هفته"})
    return sorted(rows, key=lambda r: -(r["gap"]))


def run(progress=None, sleep=time.sleep, n: int = 250) -> dict:
    """Weekly: the best-suited categories (fit 2 first), at most n, ~7 s each (Basalam is read gently)."""
    if not categories(0):
        build(C.secret("OPENROUTER_API_KEY"))
    cats = (categories(2) + [c for c in categories(1) if c["fit"] == 1])[:n]
    return measure(cats, progress=progress, sleep=sleep)


def trends(n: int = 150) -> dict:
    """Monthly, ~$0.25: 5 years of Google Trends Iran for the top categories, plus the accuracy test at category level."""
    from . import backtest
    rows = board()
    kws = [r["q"] for r in rows[:n]] or [c["fa"] for c in categories(2)[:n]]
    return backtest.run_trends(C.secret("APIFY_TOKEN"), "categories", kws=kws)
