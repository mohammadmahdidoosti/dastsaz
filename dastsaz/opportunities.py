"""Opportunity finder (step 1) and the weekly test list.

1. Seeds: motifs that sell this week on Basalam, plus styles/motifs/materials that are hot on Etsy but rare
   on Basalam.
2. Expansion: each seed is searched slowly on Basalam with every main jewelry type ("گوشواره پاپیون"...).
   One page of best-sellers + Basalam's total number of products for that search.
3. Signals per search: demand (sales this week of the top 10), supply (how many products Basalam has),
   momentum (this week's share of all-time sales: high = recently hot), price range, weak best-sellers.
4. Test list: the best 10-20 searches (diverse), each with reference photos, price range, reason and a
   short brief for the maker written by the AI. Numbers never come from the AI.

Shein's idea in small: make few pieces of many designs, measure, reorder the winners. This picks the designs.
"""
from __future__ import annotations

import json
import logging
import math
import re
import statistics
from collections import Counter, defaultdict
from urllib.parse import quote

import requests

from . import analyze as A
from . import basalam, digikala
from . import config as C

log = logging.getLogger(__name__)

TYPES = ["گردنبند", "گوشواره", "دستبند", "انگشتر"]
# Etsy style -> a word an Iranian buyer would search on Basalam
STYLE_WORD = {"وینتیج": "وینتیج", "گل و طبیعت": "گل", "اسم و حروف": "اسم", "بوهو": "بوهو",
              "سنتی و قومی": "سنتی", "مدرن هندسی": "هندسی", "کلاسیک و لوکس": "لوکس",
              "فانتزی و بامزه": "فانتزی", "مینیمال": "مینیمال"}
MATERIAL_WORD = {"روکش طلا": "روکش طلا", "نقره": "نقره", "سنگ طبیعی": "سنگ طبیعی", "مروارید": "مروارید",
                 "رزین": "رزین", "چوب": "چوبی", "چرم": "چرمی", "مهره و منجوق": "منجوق"}
NO_MOTIF = {"", "بدون طرح", "ساده", "سایر", "ندارد", "-"}
EXPAND_MAX = 60


def _plain(t: str) -> str:
    """For matching titles: half-space = space (سه‌چرخه matches سه چرخه), Arabic ي/ك as Persian, one space."""
    t = str(t or "").replace("\u200c", " ").replace("ي", "ی").replace("ك", "ک")
    return re.sub(r"\s+", " ", t).strip()


def norm_motif(m: str) -> str:
    m = re.sub(r"^(طرح|نقش|شکل|فرم)\s+", "", str(m or "").strip())
    m = re.sub(r"\s+", " ", m)
    return "" if m in NO_MOTIF else m


def seeds(etsy: list[dict], bas: list[dict], n_bas: int = 8, n_etsy: int = 6) -> list[dict]:
    """[{term, why, source}] in priority order, unique terms."""
    out, seen = [], set()

    def add(term, why, source):
        term = term.strip()
        if term and term not in seen:
            seen.add(term)
            out.append({"term": term, "why": why, "source": source})

    week = defaultdict(int)
    cnt = Counter()
    for p in bas:
        m = norm_motif(p.get("motif"))
        if m:
            week[m] += int(p.get("sales_week") or 0)
            cnt[m] += 1
    for m, w in sorted(week.items(), key=lambda kv: -kv[1]):
        if cnt[m] >= 2 and len([s for s in out if s["source"] == "basalam"]) < n_bas:
            add(m, f"در باسلام {w} فروش این هفته در {cnt[m]} محصول پرفروش", "basalam")

    def share(items, field, val):
        return 100 * sum(1 for x in items if x.get(field) == val) / (len(items) or 1)

    gaps = []
    for st, word in STYLE_WORD.items():
        g = share(etsy, "style", st) - share(bas, "style", st)
        if g >= 4:
            gaps.append((g, word, f"سبک «{st}» در اتسی {g:.0f}٪ بیشتر از باسلام"))
    for mt, word in MATERIAL_WORD.items():
        g = share(etsy, "material", mt) - share(bas, "material", mt)
        if g >= 4:
            gaps.append((g, word, f"جنس «{mt}» در اتسی {g:.0f}٪ بیشتر از باسلام"))
    em = Counter(norm_motif(x.get("motif")) for x in etsy)
    bm = Counter(norm_motif(x.get("motif")) for x in bas)
    for m, c in em.most_common(12):
        if m and c >= 3 and bm.get(m, 0) <= 1:
            gaps.append((c * 2, m, f"نقش «{m}» در {c} پرفروش اتسی، در باسلام تقریباً نیست"))
    k = 0
    for _, word, why in sorted(gaps, key=lambda g: -g[0]):
        if k >= n_etsy:
            break
        if word not in seen:
            add(word, why, "etsy")
            k += 1
    return out


def queries(sd: list[dict], limit: int = EXPAND_MAX) -> list[dict]:
    out = []
    for s in sd:
        for t in TYPES:
            out.append({"q": f"{t} {s['term']}", "type": t, **s})
    return out[:limit]


def relevant(q: str, cards: list[dict]) -> int:
    """How many results really are this design: all words of the search in the title."""
    words = [w for w in _plain(q).split() if len(w) > 1]
    return sum(1 for c in cards if all(w in _plain(c.get("title")) for w in words))


def signals(q: dict, cards: list[dict], total: int) -> dict:
    top = sorted(cards, key=lambda c: -(c.get("sales_total") or 0))[:10]
    rel = relevant(q["q"], top)
    week = sum(int(c.get("sales_week") or 0) for c in top)
    alltime = sum(int(c.get("sales_total") or 0) for c in top)
    prices = sorted(c["price_toman"] for c in top if c.get("price_toman"))
    ratings = [c["rating"] for c in top if c.get("rating")]
    weak = [c for c in top if (c.get("sales_total") or 0) >= 50 and c.get("rating") and c["rating"] < 4.3]
    shops = len({c.get("shop") for c in top if c.get("shop")})
    momentum = week / alltime if alltime else 0.0
    q25 = q75 = None
    if len(prices) >= 3:
        qs = statistics.quantiles(prices, n=4)
        q25, q75 = qs[0], qs[2]
    elif prices:
        q25, q75 = prices[0], prices[-1]
    score = (week + alltime / 52) / math.log10(total + 10)
    return {**q, "supply": total, "week": week, "alltime": alltime, "momentum": round(momentum, 3),
            "price_low": q25, "price_high": q75, "price_median": statistics.median(prices) if prices else None,
            "rating": round(statistics.mean(ratings), 2) if ratings else None, "shops": shops,
            "weak": [{"title": c["title"], "url": c["url"], "rating": c["rating"], "sales": c["sales_total"]}
                     for c in weak[:3]],
            "images": [{"src": c["image"], "url": c["url"], "title": c["title"]} for c in top if c.get("image")][:4],
            "score": round(score, 2), "labels": [], "match": rel}


def _q(vals: list[float], p: float) -> float:
    v = sorted(vals)
    return v[min(len(v) - 1, int(len(v) * p))] if v else 0.0


def relabel(opps: list[dict]) -> list[dict]:
    """Labels relative to this run's own numbers (Basalam's sales per week are small and vary by season):
    high demand = top quarter of weekly sales (at least 10); low supply = at most 500 products or the lowest
    quarter; on the rise = at least twice the median 'fresh heat' with real sales this week."""
    if not opps:
        return opps
    hi_week = max(10, _q([o["week"] for o in opps], 0.75))
    lo_supply = max(500, _q([o["supply"] for o in opps], 0.25))
    mid_mom = _q([o["momentum"] for o in opps], 0.5)
    mid_week = max(3, _q([o["week"] for o in opps], 0.5))
    hi_dk = max(50, _q([o.get("dk_reviews", 0) for o in opps if "dk_match" in o] or [0], 0.75))
    for o in opps:
        lab = []
        if o["momentum"] >= max(0.02, 2 * mid_mom) and o["week"] >= mid_week:
            lab.append("در حال اوج")
        if o["week"] >= hi_week and o["supply"] <= lo_supply:
            lab.append("تقاضای زیاد، رقیب کم")
        if o["source"] == "etsy" and o["week"] >= 3 and o["supply"] <= 1000:
            lab.append("ترند جهانی، تازه در ایران")
        if o["source"] == "google" and o["week"] >= 1:
            lab.append("جست‌وجوی تازه در گوگل")
        if o["source"] == "suggest" and o["week"] >= 1:
            lab.append("در جست‌وجوی مردم")
        if o["source"] == "etsy" and o["supply"] < 30:
            lab.append("بازار خالی (آزمایش جسورانه)")
        if o.get("weak"):
            lab.append("پرفروش ولی ضعیف")
        if o["supply"] >= 3000:
            lab.append("رقابت سنگین")
        if "dk_match" in o:
            if o["dk_match"] <= 1 and o["week"] >= hi_week:
                lab.append("در دیجی‌کالا کم‌رقیب")
            if o.get("dk_reviews", 0) >= hi_dk:
                lab.append("در دیجی‌کالا هم پرفروش")
        o["labels"] = lab
    return opps


def expand(etsy, bas, progress=None, session=None, sleep=None) -> list[dict]:
    return run_queries(queries(seeds(etsy, bas)), progress, session, sleep)


def google_queries(ideas: list[str], source: str = "google") -> list[dict]:
    why = {"google": "«{t}» از جست‌وجوهای تازه‌ی گوگل ایران است (فقط منبع ایده؛ رشد اخیر به‌تنهایی پیش‌بینی‌کننده نیست)",
           "suggest": "«{t}» از پیشنهادهای جست‌وجوی دیجی‌کالا است؛ یعنی مردم زیاد تایپش می‌کنند"}[source]
    out = []
    for t in ideas:
        typ = next((ty for ty in TYPES + ["پابند", "آویز", "ست"] if ty in t), "سایر")
        out.append({"q": t, "type": typ, "term": t, "why": why.format(t=t), "source": source})
    return out


def run_queries(qs: list[dict], progress=None, session=None, sleep=None) -> list[dict]:
    kw = {"session": session or basalam._session()}
    if sleep:
        kw["sleep"] = sleep
    out = []
    for i, q in enumerate(qs):
        try:
            cards, total = basalam.search(q["q"], **kw)
            out.append(signals(q, cards, total))
        except RuntimeError:
            raise
        except Exception as e:  # noqa: BLE001
            log.warning("expand %s: %s", q["q"], e)
        if progress:
            progress(i + 1, len(qs))
    return relabel(out)


def add_digikala(opps: list[dict], progress=None, session=None, sleep=None) -> list[dict]:
    """Same searches on Digikala: how many products it has (competition there) and whether its best-sellers
    for the search are proven (number of ratings of the top 10). Only searches not done yet."""
    todo = [o for o in opps if "dk_match" not in o]
    if not todo:
        return opps
    kw = {"session": session or digikala._session()}
    if sleep:
        kw["sleep"] = sleep
    for i, o in enumerate(todo):
        try:
            cards, total = digikala.search(o["q"], **kw)
            # Digikala's total stops near 900 (45 pages), so it is no measure of competition: count instead how
            # many of its 20 best-sellers for the search really are this design (the words of the search in the title)
            words = [w for w in _plain(o["q"]).split() if len(w) > 1]
            match = [c for c in cards if all(w in _plain(c["title"]) for w in words)]
            top = match[:10]
            prices = sorted(c["price_toman"] for c in top if c.get("price_toman"))
            o.update({"dk_supply": total, "dk_match": len(match), "dk_reviews": sum(c.get("reviews") or 0 for c in top),
                      "dk_price_median": statistics.median(prices) if prices else None,
                      "dk_images": [{"src": c["image"], "url": c["url"], "title": c["title"]}
                                    for c in top if c.get("image")][:2],
                      "dk_link": "https://www.digikala.com/search/?q=" + quote(o["q"]) + "&sort=7"})
        except RuntimeError:
            raise
        except Exception as e:  # noqa: BLE001
            log.warning("digikala expand %s: %s", o["q"], e)
        if progress:
            progress(i + 1, len(todo))
    return relabel(opps)


def pick(opps: list[dict], n: int = 15, per_seed: int = 2, per_type: int = 5) -> list[dict]:
    """Best searches for the test list: some demand or a clear global trend, not crowded, diverse.
    Never a brand's design (legal risk)."""
    from .trends import BRANDS
    ok = [o for o in opps if "رقابت سنگین" not in o["labels"] and not BRANDS.search(o["q"]) and o.get("match", 10) >= 3 and (o["week"] >= 3 or "بازار خالی (آزمایش جسورانه)"
                                                                       in o["labels"])]
    strong = {"در حال اوج": 3, "تقاضای زیاد، رقیب کم": 4, "ترند جهانی، تازه در ایران": 2,
              "بازار خالی (آزمایش جسورانه)": 1, "پرفروش ولی ضعیف": 1, "در دیجی‌کالا هم پرفروش": 2,
              "در دیجی‌کالا کم‌رقیب": 1, "جست‌وجوی تازه در گوگل": 1, "در جست‌وجوی مردم": 2}
    ok.sort(key=lambda o: (-sum(strong.get(l, 0) for l in o["labels"]), -o["score"]))
    out, by_seed, by_type = [], Counter(), Counter()
    for o in ok:
        if by_seed[o["term"]] >= per_seed or by_type[o["type"]] >= per_type:
            continue
        out.append(o)
        by_seed[o["term"]] += 1
        by_type[o["type"]] += 1
        if len(out) >= n:
            break
    return out


def etsy_refs(etsy: list[dict], term: str, typ: str, n: int = 2) -> list[dict]:
    hit = [x for x in etsy if term in (norm_motif(x.get("motif")) + " " + (x.get("name_fa") or "") + " "
                                       + STYLE_WORD.get(x.get("style"), "") + " "
                                       + MATERIAL_WORD.get(x.get("material"), ""))]
    same = [x for x in hit if x.get("type") == typ] + [x for x in hit if x.get("type") != typ]
    return [{"src": x["image"], "url": x["url"], "title": x.get("name_fa") or x["title"]} for x in same
            if x.get("image")][:n]


BRIEF_ASK = """برای یک تولیدکننده‌ی ایرانی جواهرات دست‌ساز، برای هر طرح زیر:
- name: یک نام کوتاه و جذاب فارسی برای طرح (حداکثر ۶ کلمه)
- brief: دو جمله‌ی ساده برای سازنده: شکل، جنس، رنگ و اندازه‌ی پیشنهادی. طرح هیچ فروشنده‌ی مشخصی را کپی نکن؛
  فقط ترند را به طرح خودمان تبدیل کن.
فقط JSON بده: {"items": [{"i": 0, "name": "...", "brief": "..."}]}
طرح‌ها:
"""


def briefs(items: list[dict], key: str) -> tuple[dict, float]:
    if not key or not items:
        return {}, 0.0
    data = [{"i": i, "search": o["q"], "why": o["why"], "labels": o["labels"],
             "sample_titles": [im["title"][:60] for im in o["images"][:3]]} for i, o in enumerate(items)]
    body = {"model": C.AI_MODEL, "max_tokens": 4000, "temperature": 0.4, "reasoning": {"enabled": False},
            "messages": [{"role": "user", "content": BRIEF_ASK + json.dumps(data, ensure_ascii=False)}]}
    try:
        r = requests.post(A.OPENROUTER, json=body, timeout=120, headers={
            "Authorization": f"Bearer {key}", "Content-Type": "application/json", "X-Title": "Dastsaz trends"})
        j = r.json()
        txt = ((j.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
        m = re.search(r"\{.*\}", txt, re.S)
        rows = json.loads(m.group(0)).get("items", []) if m else []
        return {int(x["i"]): x for x in rows if isinstance(x, dict) and "i" in x}, \
            float((j.get("usage") or {}).get("cost") or 0)
    except Exception as e:  # noqa: BLE001
        log.warning("briefs failed: %s", e)
        return {}, 0.0


def test_list(opps: list[dict], etsy: list[dict], key: str) -> tuple[list[dict], float]:
    chosen = pick(opps)
    br, usd = briefs(chosen, key)
    out = []
    for i, o in enumerate(chosen):
        b = br.get(i, {})
        out.append({**o, "name": str(b.get("name") or o["q"]), "brief": str(b.get("brief") or ""),
                    "etsy_refs": etsy_refs(etsy, o["term"], o["type"]) if o["source"] == "etsy" else [],
                    "basalam_link": "https://basalam.com/s?q=" + quote(o["q"])})
    return out, usd
