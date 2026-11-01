"""Digikala best-sellers, read slowly from the public search the digikala.com web app uses
(api.digikala.com/v1/search/, sort=7 = «پرفروش‌ترین»). No login, no key. Works from our VPS (tested 2026-11-01).

Digikala shows no sales count: the order of its best-seller sort and the number of ratings stand in for it.
Prices come in Rial; we keep Toman.
"""
from __future__ import annotations

import logging
import random
import time

from . import config as C

log = logging.getLogger(__name__)
URL = "https://api.digikala.com/v1/search/"
HEADERS = {"Accept": "application/json", "Accept-Language": "fa-IR,fa;q=0.9",
           "Origin": "https://www.digikala.com", "Referer": "https://www.digikala.com/"}
SORT_BESTSELLING = 7
PAGE = 20          # fixed by Digikala


def _session():
    from curl_cffi import requests as cr
    s = cr.Session(impersonate="chrome")
    s.headers.update(HEADERS)
    return s


def card(p: dict, query: str, position: int) -> dict:
    v = p.get("default_variant") if isinstance(p.get("default_variant"), dict) else {}
    price = (v.get("price") or {}).get("selling_price")
    r = p.get("rating") or {}
    img = ((p.get("images") or {}).get("main") or {}).get("url") or [""]
    uri = (p.get("url") or {}).get("uri") or f"/product/dkp-{p.get('id')}/"
    return {
        "source": "digikala", "id": str(p.get("id")), "title": p.get("title_fa") or "",
        "url": "https://www.digikala.com" + uri.split("?")[0], "image": (img[0] or "").split("?")[0],
        "price_toman": round(price / 10) if price else None, "price_usd": None,
        "sales_total": 0, "sales_week": None, "bought_24h": None, "in_cart": None,
        "rating": round((r.get("rate") or 0) / 20, 2) or None,      # Digikala rates 0-100
        "reviews": int(r.get("count") or 0), "category": ((p.get("data_layer") or {}).get("item_category5") or ""),
        "shop": (p.get("data_layer") or {}).get("brand") or "", "shop_city": "", "query": query,
        "position": position, "tags": "", "materials": "", "available": bool(price),
    }


def _get(s, params: dict, sleep) -> dict | None:
    for attempt in range(3):
        try:
            r = s.get(URL, params=params, timeout=25)
            if r.status_code == 200:
                return r.json().get("data") or {}
            log.warning("digikala %s HTTP %s", params.get("q"), r.status_code)
            if r.status_code in (403, 451):
                raise RuntimeError(f"دیجی‌کالا درخواست را مسدود کرد ({r.status_code})")
        except RuntimeError:
            raise
        except Exception as e:  # noqa: BLE001
            log.warning("digikala %s: %s", params.get("q"), e)
        sleep(20 * (attempt + 1))
    return None


def search(q: str, session=None, sleep=time.sleep) -> tuple[list[dict], int]:
    """First page (20) of best-sellers for q and Digikala's total number of products for q."""
    s = session or _session()
    sleep(random.uniform(*C.BASALAM_DELAY))
    data = _get(s, {"q": q, "sort": SORT_BESTSELLING, "page": 1}, sleep) or {}
    rows = data.get("products") or []
    total = int((data.get("pager") or {}).get("total_items") or len(rows))
    return [card(p, q, i + 1) for i, p in enumerate(rows)], total


def fetch(queries: list[str] | None = None, per_query: int | None = None, progress=None,
          session=None, sleep=time.sleep) -> list[dict]:
    queries = queries or C.BASALAM_QUERIES
    per_query = per_query or C.DIGIKALA_PER_QUERY
    s = session or _session()
    seen: set[str] = set()
    out: list[dict] = []
    for qi, q in enumerate(queries):
        pos = 0
        for page in range(1, (per_query + PAGE - 1) // PAGE + 1):
            sleep(random.uniform(*C.BASALAM_DELAY))
            rows = (_get(s, {"q": q, "sort": SORT_BESTSELLING, "page": page}, sleep) or {}).get("products") or []
            for p in rows:
                pos += 1
                c = card(p, q, pos)
                if c["id"] not in seen and c["available"]:
                    seen.add(c["id"])
                    out.append(c)
            if len(rows) < PAGE:
                break
        if progress:
            progress(qi + 1, len(queries))
        log.info("digikala %s: %d so far", q, len(out))
    return out
