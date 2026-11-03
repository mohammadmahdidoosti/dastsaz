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


CLAUDE = Path(__file__).resolve().parent / "claude_categories.tsv"


def _ai_categories() -> list[dict]:
    f = _dir() / "categories.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else []


def categories(min_fit: int = 1) -> list[dict]:
    """Persian names: Claude's hand translation of the whole Etsy list (tested: finds matching products about twice
    as often as the bulk AI's); the bulk AI file only as a fallback."""
    if CLAUDE.exists():
        rows = CLAUDE.read_text(encoding="utf-8").splitlines()[1:]
        cats = [dict(zip(("top", "name", "fa", "fit"), r.split("\t"))) for r in rows if r.count("\t") == 3]
        for c in cats:
            c["fit"] = int(c["fit"])
    else:
        cats = _ai_categories()
    return [c for c in cats if c.get("fit", 0) >= min_fit]


def measure(cats: list[dict], progress=None, sleep=time.sleep) -> dict:
    """One slow Basalam search (+ one Digikala) per category."""
    import requests
    sb, sd, sg = basalam._session(), digikala._session(), requests.Session()
    snap = {"date": C.today().isoformat(), "cats": {}}
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


# Google suggestions are 10/10 for most terms, so they can't rank; they are a check instead: 0 = Iranians don't
# type this phrase on Google, so the Persian name is probably wrong (shown as a warning, not in the score).
SOURCES = [("week", "باسلام"), ("dk_reviews", "دیجی‌کالا"), ("ads", "Ads"), ("ig", "اینستاگرام")]


ADS_SNAPSHOT = Path(__file__).resolve().parent / "ads_snapshot.json"


def _ads_map() -> dict:
    """Monthly Google searches per term: the Keyword Planner snapshot in the repo (Persian-speaking countries),
    overridden by any newer file uploaded on /ads."""
    out = {}
    try:
        snap = json.loads(ADS_SNAPSHOT.read_text(encoding="utf-8"))
        out = {_plain(r["keyword"]): r.get("avg") for r in snap["rows"] if r.get("avg") is not None}
    except Exception:  # noqa: BLE001
        pass
    try:
        from . import ads
        out.update({_plain(r["keyword"]): r.get("avg") for r in ads.latest()[1] if r.get("avg") is not None})
    except Exception:  # noqa: BLE001
        pass
    return out


def combine(rows: list[dict], weights: dict | None = None) -> list[dict]:
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
    if weights is None:
        from . import weights as W
        w = W.load()
        weights = w.get("weights") if w.get("active") else {}
    for r in rows:
        p = r.get("pct") or {}
        ws = {k: (weights or {}).get(k, 1.0) for k in p}
        tot = sum(ws.values())
        r["score"] = sum(p[k] * ws[k] for k in p) / tot if tot else 0.0
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


CORE = {  # the plain words Iranians actually type; Etsy's deep names miss them
    "Jewellery": ["گردنبند", "گوشواره", "دستبند", "انگشتر", "پابند", "آویز گردنبند", "سرویس جواهرات", "گردنبند اسم",
                  "دستبند چرم", "گوشواره میخی", "گردنبند استیل", "دستبند نقره", "انگشتر نقره", "زیورآلات دست ساز",
                  # men's (Twitter: birthday gifts for boyfriends are a big need)
                  "دستبند مردانه", "انگشتر مردانه", "گردنبند مردانه", "زنجیر مردانه", "دستبند چرم مردانه",
                  "انگشتر عقیق", "دستبند اسم مردانه", "پلاک اسم مردانه", "دکمه سردست", "گیره کراوات"],
    "Accessories": ["گیره مو", "کش مو", "شال", "روسری", "کلاه", "عینک آفتابی", "کمربند", "جاکلیدی", "کیف پول"],
    "Bags & Purses": ["کیف دستی", "کیف دوشی", "کوله پشتی", "کیف آرایش"],
    "Home & Living": ["شمع", "گلدان", "تابلو", "ماگ", "کوسن", "رومیزی", "جاشمعی", "دیوارکوب"],
    "Bath & Beauty": ["صابون", "بالم لب", "شمع معطر", "روغن مو"],
    "Weddings": ["کادو عروسی", "گیفت عروسی", "تاج عروس"],
    "Paper & Party Supplies": ["کارت پستال", "دفتر", "تزیینات تولد", "باکس هدیه"],
    "Toys & Games": ["عروسک", "اسباب بازی چوبی", "پازل"],
}


def pick(cats: list[dict], n: int) -> list[dict]:
    """n categories spread evenly over Etsy's main groups (jewellery, home, toys...), best fit first in each group,
    one per Persian search term. Taking the first n of the list would read only the first groups."""
    groups: dict[str, list] = {}
    seen: set[str] = set()
    core = [{"top": top, "name": "core", "fa": w, "fit": 2} for top, ws in CORE.items() for w in ws]
    for c in core + sorted(cats, key=lambda c: -c["fit"]):
        k = _plain(c["fa"])
        if k and k not in seen:
            seen.add(k)
            groups.setdefault(c["top"], []).append(c)
    out, i = [], 0
    while len(out) < n and any(i < len(g) for g in groups.values()):
        for g in groups.values():
            if i < len(g) and len(out) < n:
                out.append(g[i])
        i += 1
    return out


def run(progress=None, sleep=time.sleep, n: int = 400) -> dict:
    """Weekly: the best-suited categories (fit 2 first), at most n, ~7 s each (Basalam is read gently);
    then Instagram hashtags for the same categories if an Apify key is set (~$0.35)."""
    if not categories(0):
        build(C.secret("OPENROUTER_API_KEY"))
    snap = measure(pick(categories(1), n), progress=progress, sleep=sleep)
    try:
        from . import weights as W
        W.save(W.learn(history()))
    except Exception as e:  # noqa: BLE001
        log.warning("radar weights: %s", e)
    if C.secret("APIFY_TOKEN"):
        try:
            instagram()
        except Exception as e:  # noqa: BLE001
            log.warning("radar instagram: %s", e)
    return history()[-1] if history() else snap


IG_ACTOR = "apify~instagram-hashtag-scraper"   # hashtag-stats returns 0 for every Persian tag; recent posts work


def hashtag(q: str) -> str:
    return re.sub(r"\s+", "_", _plain(q))


def _ig_stats(posts: list[dict]) -> dict:
    """Recent posts of one hashtag -> new posts per day, distinct accounts posting, median likes."""
    ts = sorted(dt.datetime.fromisoformat(str(x["timestamp"]).replace("Z", "+00:00")) for x in posts if x.get("timestamp"))
    if len(ts) < 2:
        return {"ig_day": 0.0 if ts else None, "ig_sellers": len({x.get("ownerUsername") for x in posts}), "ig_likes": None}
    days = max((ts[-1] - ts[0]).total_seconds() / 86400, 1 / 24)
    likes = sorted(int(x.get("likesCount") or 0) for x in posts if str(x.get("likesCount") or "0").lstrip("-").isdigit())
    return {"ig_day": round((len(ts) - 1) / days, 1), "ig_sellers": len({x.get("ownerUsername") for x in posts}),
            "ig_likes": likes[len(likes) // 2] if likes else None}


def instagram(token: str | None = None, n: int = 60, explore: int = 0, per: int = 12, max_usd: float = 2.0, ap=None) -> int:
    """For the top n categories of the latest radar week and `explore` random others: how fast new posts appear under the Persian hashtag
    (posts per day), how many accounts post, median likes. ~$0.03 per category. Written into that week."""
    from urllib.parse import unquote
    from .etsy import Apify
    if not history():
        return 0
    f = sorted(_dir().glob("20*.json"))[-1]
    snap = json.loads(f.read_text(encoding="utf-8"))
    ranked = [r for r in board() if r.get("week") is not None]
    rest = ranked[n:]
    # optional random sample of the rest; tested 2026-11-03 with 60: only 1 of 60 was busy on Instagram, so off by default
    rows = ranked[:n] + random.Random(snap["date"]).sample(rest, min(explore, len(rest)))
    tags = {hashtag(r["q"]): r["q"] for r in rows}
    ap = ap or Apify(token or C.secret("APIFY_TOKEN"))
    run = ap.run({"hashtags": list(tags), "resultsLimit": per}, max_usd, actor=IG_ACTOR)
    items = ap.items(run["defaultDatasetId"]) if run.get("defaultDatasetId") else []
    by: dict[str, list] = {}
    for it in items:
        tag = _plain(unquote(str(it.get("inputUrl") or "")).rstrip("/").rsplit("/", 1)[-1])
        if tag in tags:
            by.setdefault(tag, []).append(it)
    for tag, q in tags.items():
        st = _ig_stats(by.get(tag, []))
        snap["cats"][q].update(st)
        snap["cats"][q]["ig"] = st["ig_day"]
    snap["ig_usd"] = ap.cost(run)
    f.write_text(json.dumps(snap, ensure_ascii=False), encoding="utf-8")
    log.info("radar instagram: %d of %d hashtags had posts, $%.2f", len(by), len(tags), snap["ig_usd"])
    return len(by)


def trends(n: int = 150) -> dict:
    """Monthly, ~$0.25: 5 years of Google Trends Iran for the top categories, plus the accuracy test at category level."""
    from . import backtest
    rows = board()
    kws = [r["q"] for r in rows[:n]] or [c["fa"] for c in categories(2)[:n]]
    return backtest.run_trends(C.secret("APIFY_TOKEN"), "categories", kws=kws)


def _probe(q: str, sb, sd, sg, sleep) -> dict:
    """One term on Basalam, Digikala and Google: does it find matching products / searches?"""
    from .needs import google_suggest
    words = [w for w in _plain(q).split() if len(w) > 1]
    out = {"q": q}
    try:
        cards, total = basalam.search(q, size=20, session=sb, sleep=sleep)
        m = [x for x in cards if all(w in _plain(x.get("title")) for w in words)]
        out.update({"bs_match": len(m), "bs_week": sum(x["sales_week"] for x in m[:15])})
    except Exception as e:  # noqa: BLE001
        log.warning("probe basalam %s: %s", q, e)
    try:
        dc, _ = digikala.search(q, session=sd, sleep=lambda *_: time.sleep(random.uniform(1, 2)))
        out["dk_match"] = sum(1 for x in dc if all(w in _plain(x.get("title")) for w in words))
    except Exception as e:  # noqa: BLE001
        log.warning("probe digikala %s: %s", q, e)
    out["g"] = sum(1 for x in google_suggest(sg, q) if all(w in _plain(x) for w in words))
    return out


def translation_test(progress=None, sleep=time.sleep) -> dict:
    """Same 150 Etsy categories, two Persian names: the bulk AI's and Claude's (dastsaz/translation_test.json).
    Which name finds more matching products on Basalam/Digikala and more Google searches?"""
    import requests
    sample = json.loads((Path(__file__).resolve().parent / "translation_test.json").read_text(encoding="utf-8"))
    ai_fa = {(c["top"], c["name"]): c for c in _ai_categories()}
    sb, sd, sg = basalam._session(), digikala._session(), requests.Session()
    rows, cache = [], {}
    for i, c in enumerate(sample):
        a = ai_fa.get((c["top"], c["name"])) or {}
        row = {"top": c["top"], "name": c["name"], "ai": a.get("fa") or "", "ai_fit": a.get("fit"),
               "claude": c["claude"], "claude_fit": c["claude_fit"]}
        for side in ("ai", "claude"):
            q = row[side]
            if q and _plain(q) not in cache:
                cache[_plain(q)] = _probe(q, sb, sd, sg, sleep)
            row[side + "_r"] = cache.get(_plain(q)) if q else {}
        rows.append(row)
        if progress:
            progress(i + 1, len(sample))

    def summary(side):
        rs = [r[side + "_r"] for r in rows if r[side + "_r"]]
        n = len(rs) or 1
        return {"n": len(rs), "bs_found": sum(1 for r in rs if r.get("bs_match")) / n,
                "dk_found": sum(1 for r in rs if r.get("dk_match")) / n, "google_found": sum(1 for r in rs if r.get("g")) / n,
                "bs_week": sum(r.get("bs_week") or 0 for r in rs)}
    diff = [r for r in rows if _plain(r["ai"]) != _plain(r["claude"])]
    res = {"date": C.today().isoformat(), "ai": summary("ai"), "claude": summary("claude"), "differ": len(diff),
           "fit_same": sum(1 for r in rows if r["ai_fit"] == r["claude_fit"]), "rows": rows}
    (_dir() / "translation_test_result.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    return res
