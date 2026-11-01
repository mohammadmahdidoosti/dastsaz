"""Builds the Persian trend report (one self-contained HTML page) from the classified products."""
from __future__ import annotations

import json
import logging
import statistics
from collections import Counter
from pathlib import Path


from . import analyze as A
from . import config as C

log = logging.getLogger(__name__)
from .page import fa, jalali  # noqa: E402,F401  (kept here for older callers)


def shares(items: list[dict], field: str) -> dict[str, float]:
    c = Counter(x.get(field) or "سایر" for x in items)
    n = sum(c.values()) or 1
    return {k: v * 100 / n for k, v in c.items()}


def compare(etsy: list[dict], bas: list[dict], field: str, order: list[str], dk: list[dict] | None = None) -> list[dict]:
    e, b, d = shares(etsy, field), shares(bas, field), shares(dk or [], field)
    rows = [{"name": k, "etsy": e.get(k, 0.0), "basalam": b.get(k, 0.0), "digikala": d.get(k, 0.0),
             "gap": e.get(k, 0.0) - b.get(k, 0.0)} for k in order if e.get(k) or b.get(k) or d.get(k)]
    return sorted(rows, key=lambda r: -(r["etsy"] + r["basalam"]))


def price_stats(vals: list[float]) -> dict | None:
    v = sorted(x for x in vals if x)
    if len(v) < 3:
        return None
    q = statistics.quantiles(v, n=4)
    return {"n": len(v), "low": q[0], "median": statistics.median(v), "high": q[2]}


def prices_by_type(etsy, bas, dk=None) -> list[dict]:
    rows = []
    for t in A.TYPES:
        e = price_stats([x["price_usd"] for x in etsy if x["type"] == t])
        b = price_stats([x["price_toman"] for x in bas if x["type"] == t])
        d = price_stats([x["price_toman"] for x in (dk or []) if x["type"] == t])
        if e or b or d:
            rows.append({"type": t, "etsy": e, "basalam": b, "digikala": d})
    return rows


def counts(items, field, n=12) -> list[tuple[str, int]]:
    return Counter(x[field] for x in items if x.get(field)).most_common(n)


def stats(etsy: list[dict], bas: list[dict], dk: list[dict] | None = None) -> dict:
    dk = dk or []
    return {
        "n_etsy": len(etsy), "n_basalam": len(bas), "n_digikala": len(dk),
        "type": compare(etsy, bas, "type", A.TYPES, dk), "style": compare(etsy, bas, "style", A.STYLES, dk),
        "material": compare(etsy, bas, "material", A.MATERIALS, dk),
        "color": compare(etsy, bas, "color", A.COLORS, dk),
        "prices": prices_by_type(etsy, bas, dk),
        "motif_digikala": counts(dk, "motif"), "stone_digikala": counts(dk, "stone", 8),
        "personal_digikala": sum(1 for x in dk if x["personalized"]) * 100 / (len(dk) or 1),
        "motif_etsy": counts(etsy, "motif"), "motif_basalam": counts(bas, "motif"),
        "stone_etsy": counts(etsy, "stone", 8), "stone_basalam": counts(bas, "stone", 8),
        "personal_etsy": sum(1 for x in etsy if x["personalized"]) * 100 / (len(etsy) or 1),
        "personal_basalam": sum(1 for x in bas if x["personalized"]) * 100 / (len(bas) or 1),
    }


def build(run_dir: Path, name: str, etsy: list[dict], bas: list[dict], key: str, cost_add, when: str,
          opps: list[dict] | None = None, tl: list[dict] | None = None, dk: list[dict] | None = None,
          tr: list[dict] | None = None) -> Path:
    from . import analysis as AN
    from . import costs, page
    dk = [x for x in (dk or []) if x.get("is_jewelry", True)]
    etsy = [x for x in etsy if x.get("is_jewelry", True)]
    bas = [x for x in bas if x.get("is_jewelry", True)]
    opps, tl, tr = opps or [], tl or [], tr or []
    st = stats(etsy, bas, dk)
    mid = AN.mid_week(opps)
    for o in tl:
        o["eco"] = AN.economics(o, mid)
    mk = AN.markets(etsy, bas, dk)
    ex, usd = AN.executive(st, tl, tr, mk, key)
    if usd:
        cost_add("تحلیل مدیریتی (هوش مصنوعی)", 1, usd)
    html_page = page.render(name, page.jalali(when[:10]) + when[10:], st, ex, mk, etsy, bas, dk, opps, tl, tr,
                            costs.summary(run_dir), mid)
    (run_dir / "stats.json").write_text(json.dumps({**st, "executive": ex, "markets": mk,
                                                    "points": [f["text"] for f in ex.get("findings", [])]},
                                                   ensure_ascii=False, default=str, indent=1), encoding="utf-8")
    p = run_dir / "report.html"
    p.write_text(html_page, encoding="utf-8")
    return p
