"""Weekly photo of the market: for every tracked search, Basalam's top-10 best-sellers with their «sold this week»
and «sold in all» numbers. Saved once a week, these become our own exact sales history: after 8-12 weeks the
backtest can be repeated with real weekly sales instead of review counts.

Tracked searches = the opportunity searches of the latest report + every design in the lab.
Free; read slowly (about 6 seconds a search)."""
from __future__ import annotations

import datetime as dt
import json
import logging
import time

from . import basalam
from . import config as C
from . import lab
from .opportunities import _plain

log = logging.getLogger(__name__)


def _dir():
    d = C.DATA_DIR / "snapshots"
    d.mkdir(parents=True, exist_ok=True)
    return d


def tracked(n: int = 80) -> list[str]:
    qs: list[str] = []
    runs = sorted((C.DATA_DIR / "runs").glob("*/opportunities.json"), key=lambda p: p.stat().st_mtime)
    if runs:
        opps = json.loads(runs[-1].read_text(encoding="utf-8"))
        qs = [o["q"] for o in sorted(opps, key=lambda o: -(o.get("week") or 0))]
    qs += [t["query"] or t["name"] for t in lab.load() if not t["closed"]]
    seen, out = set(), []
    for q in qs:
        if q and q not in seen:
            seen.add(q)
            out.append(q)
    return out[:n]


def take(queries: list[str] | None = None, progress=None, sleep=time.sleep) -> dict:
    queries = queries or tracked()
    s = basalam._session()
    snap = {"date": dt.date.today().isoformat(), "searches": {}}
    for i, q in enumerate(queries):
        try:
            cards, total = basalam.search(q, size=20, session=s, sleep=sleep)
            words = [w for w in _plain(q).split() if len(w) > 1]
            cards = [c for c in cards if all(w in _plain(c.get("title")) for w in words)][:10]   # only this design
            snap["searches"][q] = {"supply": total, "match": len(cards), "week": sum(c["sales_week"] for c in cards),
                                   "alltime": sum(c["sales_total"] for c in cards),
                                   "products": [{"id": c["id"], "week": c["sales_week"], "total": c["sales_total"],
                                                 "price": c["price_toman"]} for c in cards]}
        except RuntimeError:
            raise
        except Exception as e:  # noqa: BLE001
            log.warning("snapshot %s: %s", q, e)
        if progress:
            progress(i + 1, len(queries))
    (_dir() / f"{snap['date']}.json").write_text(json.dumps(snap, ensure_ascii=False), encoding="utf-8")
    return snap


def stage(sales_change, supply_change: float, supply: int) -> str:
    """Life stage of a trend (status goods die when they get common): new sellers pour in faster than buyers -> saturating."""
    if sales_change is not None and sales_change >= 0.2 and supply < 1500 and supply_change < 0.1:
        return "نوظهور"
    if supply_change >= 0.1 and (sales_change is None or sales_change < supply_change):
        return "رو به اشباع"
    if sales_change is not None and sales_change >= 0.2:
        return "در اوج"
    if sales_change is not None and sales_change <= -0.2:
        return "رو به افت"
    return "ثابت"


def history() -> list[dict]:
    return [json.loads(f.read_text(encoding="utf-8")) for f in sorted(_dir().glob("*.json"))]


def changes(hist: list[dict] | None = None) -> list[dict]:
    """Week over week for the last two photos: which searches sell more / less than last week."""
    hist = hist if hist is not None else history()
    if len(hist) < 2:
        return []
    a, b = hist[-2]["searches"], hist[-1]["searches"]
    out = []
    for q, cur in b.items():
        if q in a:
            prev = a[q]["week"]
            ch = (cur["week"] - prev) / prev if prev else None
            sup = (cur["supply"] - a[q]["supply"]) / a[q]["supply"] if a[q]["supply"] else 0.0
            out.append({"q": q, "prev": prev, "now": cur["week"], "change": ch,
                        "supply_change": cur["supply"] - a[q]["supply"], "stage": stage(ch, sup, cur["supply"])})
    return sorted(out, key=lambda r: -(r["now"] - r["prev"]))
