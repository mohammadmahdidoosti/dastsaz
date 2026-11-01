"""Which source tells early and right what Iranians will buy?

Truth = Basalam sales per design, month by month (reviews with dates, from the reviews backtest).
For each source and each Instagram page we ask: the designs it pushed (posted and got engagement on) in the
first months, did they sell more on Basalam in the following months than the average design?

score of a source = (average sales growth of its top designs) - (average growth of all designs)
hit rate         = share of its top designs whose sales grew
lead             = months between its push and Basalam's growth (best of 1..4)

Run on the server after the reviews backtest:  python -m dastsaz.signals
"""
from __future__ import annotations

import json
import logging
import re
import sys
from collections import defaultdict

from . import backtest as B
from . import config as C

log = logging.getLogger(__name__)
GENERIC = {"گردنبند", "دستبند", "انگشتر", "گوشواره", "پابند", "آویز", "زنانه", "دخترانه", "مردانه", "پسرانه", "نقره",
           "استیل", "طلا", "طلایی", "بدلیجات", "زیورآلات", "ست", "مدل", "جدید", "رنگ", "ثابت"}
TOPK = 5


def norm(t: str) -> str:
    t = str(t or "").replace("ي", "ی").replace("ك", "ک").replace("‌", " ").replace("_", " ").replace("#", " ")
    return re.sub(r"\s+", " ", t)


def motif_words(q: str) -> list[str]:
    w = [x for x in norm(q).split() if x not in GENERIC and len(x) > 1]
    return w or norm(q).split()


def mentions(caption: str, q: str) -> bool:
    c = norm(caption)
    return all(w in c for w in motif_words(q))


def basalam_truth(cat: str = "jewelry") -> tuple[dict[str, list[float]], list[str]]:
    d = C.DATA_DIR / "backtest"
    raw = json.loads((d / f"reviews_raw_{cat}.json").read_text(encoding="utf-8"))
    months = sorted({x[:7] for v in raw["products"].values() for x in v})
    series = {}
    for q, ids in raw["designs"].items():
        cnt = defaultdict(int)
        for pid in ids:
            for x in raw["products"].get(pid, []):
                cnt[x[:7]] += 1
        series[q] = [float(cnt.get(m, 0)) for m in months]
    return series, months


def instagram_push(posts: list[dict], followers: dict[str, int], designs: list[str]) -> dict:
    """page -> design -> month -> engagement (likes+comments per 1000 followers)."""
    out: dict = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))
    for p in posts:
        u = p.get("ownerUsername") or ""
        mo = str(p.get("timestamp") or "")[:7]
        if not u or not mo:
            continue
        cap = " ".join([p.get("caption") or "", " ".join(p.get("hashtags") or [])])
        eng = max(0, p.get("likesCount") or 0) + max(0, p.get("commentsCount") or 0)
        f = max(followers.get(u) or 0, 1000)
        for q in designs:
            if mentions(cap, q):
                out[u][q][mo] += eng * 1000 / f
    return out


def growth(s: list[float], months: list[str], start: str, length: int, before: int = 3):
    """sales in `length` months from `start` vs the `before` months just before it (per month)."""
    if start not in months:
        return None
    i = months.index(start)
    if i < before or i + length > len(months):
        return None
    a = sum(s[i - before:i]) / before
    b = sum(s[i:i + length]) / length
    return None if a + b < 2 else (b - a) / max(a, 1.0)


def score_source(push: dict[str, dict[str, float]], truth, months, window: list[str], lead: int) -> dict | None:
    """push: design -> month -> strength. Picks the source's top designs in `window`, checks Basalam `lead`
    months after the window."""
    tot = {q: sum(m.get(x, 0) for x in window) for q, m in push.items()}
    tot = {q: v for q, v in tot.items() if v > 0 and q in truth}
    if len(tot) < 2:
        return None
    end = window[-1]
    if end not in months or months.index(end) + lead >= len(months):
        return None
    start = months[months.index(end) + lead]
    gs = {q: growth(truth[q], months, start, 3) for q in truth}
    gs = {q: g for q, g in gs.items() if g is not None}
    top = [q for q in sorted(tot, key=lambda q: -tot[q]) if q in gs][:TOPK]
    if not top or len(gs) < 6:
        return None
    avg_all = sum(gs.values()) / len(gs)
    avg_top = sum(gs[q] for q in top) / len(top)
    return {"top": top, "hit": sum(1 for q in top if gs[q] > 0) / len(top), "lift": avg_top - avg_all,
            "base_hit": sum(1 for g in gs.values() if g > 0) / len(gs), "lead": lead, "start": start}


def evaluate_all(cat: str = "jewelry") -> dict:
    truth, months = basalam_truth(cat)
    d = C.DATA_DIR
    posts = json.loads((d / "ig_posts.json").read_text(encoding="utf-8")) if (d / "ig_posts.json").exists() else []
    pages = json.loads((d / "ig_pages.json").read_text(encoding="utf-8")) if (d / "ig_pages.json").exists() else []
    fol = {p.get("username"): p.get("followersCount") or 0 for p in pages}
    ig = instagram_push(posts, fol, list(truth))
    ig_months = sorted({str(p.get("timestamp"))[:7] for p in posts if p.get("timestamp")})
    sources: dict[str, dict] = {}
    # pooled Instagram and each page
    pooled: dict = defaultdict(lambda: defaultdict(float))
    for u, dq in ig.items():
        for q, mm in dq.items():
            for mo, v in mm.items():
                pooled[q][mo] += v
    cand = {"اینستاگرام (همه‌ی پیج‌ها)": pooled, **{f"پیج {u}": dq for u, dq in ig.items()}}
    # Digikala sales of the same designs: does Digikala move before Basalam?
    dk_f = C.DATA_DIR / "backtest" / f"reviews_raw_dk_{cat}.json"
    if dk_f.exists():
        dk = json.loads(dk_f.read_text(encoding="utf-8"))
        push_dk = {}
        for q, ids in dk["designs"].items():
            cnt = defaultdict(float)
            for pid in ids:
                for x in dk["products"].get(pid, []):
                    cnt[x[:7]] += 1
            push_dk[q] = dict(cnt)
        cand["دیجی‌کالا (فروش همان طرح)"] = push_dk
    # Basalam's own recent sales as the baseline source ("what sells now keeps selling")
    cand["خود باسلام (فروش اخیر)"] = {q: dict(zip(months, s)) for q, s in truth.items()}
    for name, push in cand.items():
        best = None
        rows = []
        for w0 in range(0, max(1, len(ig_months) - 5)):
            window = ig_months[w0:w0 + 3] if name.startswith(("اینستاگرام", "پیج")) else None
            if not name.startswith(("اینستاگرام", "پیج")) and w0 > 8:
                break
            if window is None:
                k = len(months) - 9 - w0
                if k < 3:
                    break
                window = months[k - 3:k]
            for lead in (1, 2, 3, 4):
                r = score_source(push, truth, months, window, lead)
                if r:
                    rows.append(r)
        if rows:
            by_lead = defaultdict(list)
            for r in rows:
                by_lead[r["lead"]].append(r)
            summ = {L: {"hit": sum(r["hit"] for r in v) / len(v), "lift": sum(r["lift"] for r in v) / len(v),
                        "base_hit": sum(r["base_hit"] for r in v) / len(v), "tests": len(v)}
                    for L, v in by_lead.items()}
            L, best = max(summ.items(), key=lambda kv: kv[1]["lift"])
            sources[name] = {"best_lead": L, **best, "by_lead": summ,
                             "designs": len(push), "example": rows[-1]["top"]}
    res = {"cat": cat, "months": [months[0], months[-1]] if months else [], "designs": len(truth),
           "ig_posts": len(posts), "ig_pages": len(ig), "sources": sources}
    (C.DATA_DIR / "backtest" / f"signals_{cat}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1),
                                                                  encoding="utf-8")
    return res


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    r = evaluate_all(sys.argv[1] if len(sys.argv) > 1 else "jewelry")
    print("designs", r["designs"], "ig posts", r["ig_posts"], "pages with matches", r["ig_pages"])
    for k, v in sorted(r["sources"].items(), key=lambda kv: -kv[1]["lift"]):
        print(f"{v['lift']:+.2f} hit {v['hit']:.2f} base {v['base_hit']:.2f} lead {v['best_lead']} tests {v['tests']} | {k}")
