"""The category radar: which whole categories are growing in Iran, so we hunt where the market gets bigger.

Base list: Etsy's full category tree (dastsaz/etsy_categories.txt, ~3000 names). Once, AI turns each into the Persian
words Iranians search on Basalam/Digikala and says whether a small Iranian maker could make or source it.
Every week, per category (one slow search each, free): Basalam weekly sales of the top matching products, number of
competing products, Digikala reviews of matching best-sellers, Google suggestions; plus Google Ads volume if uploaded.
One store alone is biased (Basalam buyers differ from Digikala and Instagram buyers), so the board ranks by the average
rank over all sources and shows in how many sources a category is strong; week-over-week change and life stage. Monthly (optional, ~$0.3): Google Trends
Iran 5 years -> season and long-run direction, and the same accuracy test at category level.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import random
import re
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
    import requests
    sb, sd, sg = basalam._session(), digikala._session(), requests.Session()
    snap = {"date": dt.date.today().isoformat(), "cats": {}}
    for i, c in enumerate(cats):
        q = c["fa"]
        row = {"top": c["top"], "name": c["name"], "fit": c["fit"]}
        words = [w for w in _plain(q).split() if len(w) > 1]
        try:
            cards, total = basalam.search(q, size=20, session=sb, sleep=sleep)
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
                dm = [x for x in dcards if all(w in _plain(x.get("title")) for w in words)][:10]
                row.update({"dk_total": dtotal, "dk_match": len(dm), "dk_reviews": sum(x.get("reviews") or 0 for x in dm)})
            except Exception as e:  # noqa: BLE001
                log.warning("radar digikala %s: %s", q, e)
        try:
            from .needs import google_suggest
            sug = google_suggest(sg, q)
            row["g_suggest"] = sum(1 for x in sug if all(w in _plain(x) for w in words))
        except Exception as e:  # noqa: BLE001
            log.warning("radar google %s: %s", q, e)
        snap["cats"][q] = row
        if progress:
            progress(i + 1, len(cats))
    (_dir() / f"{snap['date']}.json").write_text(json.dumps(snap, ensure_ascii=False), encoding="utf-8")
    return snap


def history() -> list[dict]:
    return [json.loads(f.read_text(encoding="utf-8")) for f in sorted(_dir().glob("20*.json"))]


SOURCES = [("week", "باسلام"), ("dk_reviews", "دیجی‌کالا"), ("g_suggest", "گوگل"), ("ads", "Ads"), ("ig", "اینستاگرام")]


def _ads_map() -> dict:
    try:
        from . import ads
        return {_plain(r["keyword"]): r.get("avg") for r in ads.latest()[1] if r.get("avg") is not None}
    except Exception:  # noqa: BLE001
        return {}


def combine(rows: list[dict]) -> list[dict]:
    """Each source ranks the categories (0 = last, 1 = first); score = average over the sources that have a number.
    agree = in how many sources the category is in the top third; strong = names of those sources."""
    for key, _ in SOURCES:
        vals = sorted(r[key] for r in rows if r.get(key) is not None)
        n = len(vals)
        if n < 2 or vals[0] == vals[-1]:
            continue
        for r in rows:
            v = r.get(key)
            if v is None:
                continue
            below = sum(1 for x in vals if x < v)
            same = sum(1 for x in vals if x == v)
            r.setdefault("pct", {})[key] = (below + (same - 1) / 2) / (n - 1)
    for r in rows:
        p = r.get("pct") or {}
        r["score"] = sum(p.values()) / len(p) if p else 0.0
        r["n_src"] = len(p)
        r["strong"] = [name for key, name in SOURCES if p.get(key, 0) >= 2 / 3]
        r["agree"] = len(r["strong"])
    return sorted(rows, key=lambda r: (-r["score"], -r["gap"]))


def board(hist: list[dict] | None = None, ads_map: dict | None = None) -> list[dict]:
    """Latest week per category: demand per competitor, week-over-week change, life stage and the multi-source score."""
    from .snapshot import stage
    hist = hist if hist is not None else history()
    if not hist:
        return []
    ads_map = _ads_map() if ads_map is None else ads_map
    cur, prev = hist[-1]["cats"], (hist[-2]["cats"] if len(hist) > 1 else {})
    rows = []
    for q, r in cur.items():
        if r.get("week") is None:
            continue
        p = prev.get(q) or {}
        ch = (r["week"] - p["week"]) / p["week"] if p.get("week") else None
        sup = (r["supply"] - p["supply"]) / p["supply"] if p.get("supply") else 0.0
        row = {"q": q, **r, "per_seller": r["week"] / max(r.get("match") or 1, 1),
               "gap": r["week"] / max(r.get("supply") or 1, 1) * 1000,
               "change": ch, "stage": stage(ch, sup, r.get("supply") or 0) if p else "اولین هفته"}
        if "dk_match" not in r:          # older weeks: Digikala reviews were not filtered for relevance
            row.pop("dk_reviews", None)
        if row.get("ads") is None and _plain(q) in ads_map:
            row["ads"] = ads_map[_plain(q)]
        rows.append(row)
    return combine(rows)


def run(progress=None, sleep=time.sleep, n: int = 250) -> dict:
    """Weekly: the best-suited categories (fit 2 first), at most n, ~7 s each (Basalam is read gently);
    then Instagram hashtags for the same categories if an Apify key is set (~$0.35)."""
    if not categories(0):
        build(C.secret("OPENROUTER_API_KEY"))
    cats = (categories(2) + [c for c in categories(1) if c["fit"] == 1])[:n]
    snap = measure(cats, progress=progress, sleep=sleep)
    if C.secret("APIFY_TOKEN"):
        try:
            instagram()
        except Exception as e:  # noqa: BLE001
            log.warning("radar instagram: %s", e)
    return history()[-1] if history() else snap


IG_ACTOR = "apify~instagram-hashtag-stats"


def hashtag(q: str) -> str:
    return re.sub(r"\s+", "_", _plain(q))


def instagram(token: str | None = None, max_usd: float = 1.0, ap=None) -> int:
    """Instagram hashtag size and posts per day for every category in the latest radar week; written into that week."""
    from .etsy import Apify
    hist = history()
    if not hist:
        return 0
    f = sorted(_dir().glob("20*.json"))[-1]
    snap = json.loads(f.read_text(encoding="utf-8"))
    tags = {hashtag(q): q for q in snap["cats"]}
    ap = ap or Apify(token or C.secret("APIFY_TOKEN"))
    run = ap.run({"hashtags": list(tags)}, max_usd, actor=IG_ACTOR)
    items = ap.items(run["defaultDatasetId"]) if run.get("defaultDatasetId") else []
    got = 0
    for it in items:
        name = _plain(str(it.get("name") or "").lstrip("#"))
        q = tags.get(name) or tags.get(hashtag(name))
        if not q:
            continue
        posts = it.get("postsCount")
        day = it.get("postsPerDay")
        row = snap["cats"][q]
        row["ig_posts"] = int(posts) if isinstance(posts, (int, float)) else None
        row["ig_day"] = float(day) if isinstance(day, (int, float)) else None
        row["ig"] = row["ig_day"] if row["ig_day"] is not None else row["ig_posts"]
        got += 1
    snap["ig_usd"] = ap.cost(run)
    f.write_text(json.dumps(snap, ensure_ascii=False), encoding="utf-8")
    log.info("radar instagram: %d of %d hashtags, $%.2f", got, len(tags), snap["ig_usd"])
    return got


def trends(n: int = 150) -> dict:
    """Monthly, ~$0.25: 5 years of Google Trends Iran for the top categories, plus the accuracy test at category level."""
    from . import backtest
    rows = board()
    kws = [r["q"] for r in rows[:n]] or [c["fa"] for c in categories(2)[:n]]
    return backtest.run_trends(C.secret("APIFY_TOKEN"), "categories", kws=kws)
