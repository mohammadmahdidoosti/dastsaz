"""Basalam best-sellers, read slowly from the public search the basalam.com web app itself uses
(services.basalam.com/web/v1/search/product/search, sort=sales). No login, no key.

Endpoint and parameters as used by the open-source basalam-mcp project. Prices come in Rial; we keep Toman.
"""
from __future__ import annotations

import logging
import random
import time

from . import config as C

log = logging.getLogger(__name__)
URL = "https://services.basalam.com/web/v1/search/product/search"
HEADERS = {"Accept": "application/json", "Accept-Language": "fa-IR,fa;q=0.9,en;q=0.8",
           "Origin": "https://basalam.com", "Referer": "https://basalam.com/"}
PAGE = 30


def _session():
    from curl_cffi import requests as cr      # Chrome-like connection, like a normal visitor
    s = cr.Session(impersonate="chrome")
    s.headers.update(HEADERS)
    return s


def _photo(p: dict) -> str:
    ph = p.get("photo") or {}
    if isinstance(ph, dict):
        for k in ("MEDIUM", "LARGE", "SMALL", "EXTRA_SMALL", "url"):
            if ph.get(k):
                return ph[k]
    for ph in p.get("photos") or []:
        if isinstance(ph, dict):
            for k in ("MEDIUM", "LARGE", "SMALL", "url"):
                if ph.get(k):
                    return ph[k]
        elif isinstance(ph, str):
            return ph
    return ""


def card(p: dict, query: str, position: int) -> dict:
    v, r = p.get("vendor") or {}, p.get("rating") or {}
    price = p.get("price")
    return {
        "source": "basalam", "id": str(p.get("id")), "title": p.get("name") or "",
        "url": f"https://basalam.com/p/{p.get('id')}", "image": _photo(p),
        "price_toman": round(price / 10) if price else None, "price_usd": None,
        "sales_total": p.get("sales_count") or 0, "sales_week": p.get("sales_count_week") or 0,
        "rating": r.get("average") or None, "reviews": r.get("count") or 0,
        "category": p.get("categoryTitle") or "", "shop": v.get("name") or "",
        "shop_city": (v.get("owner") or {}).get("city") or "", "query": query, "position": position,
        "tags": "", "materials": "", "bought_24h": None, "in_cart": None,
    }


def fetch(queries: list[str] | None = None, per_query: int | None = None, progress=None,
          session=None, sleep=time.sleep) -> list[dict]:
    queries = queries or C.BASALAM_QUERIES
    per_query = per_query or C.BASALAM_PER_QUERY
    s = session or _session()
    seen: set[str] = set()
    out: list[dict] = []
    for qi, q in enumerate(queries):
        pos = 0
        for start in range(0, per_query, PAGE):
            sleep(random.uniform(*C.BASALAM_DELAY))
            params = {"q": q, "sort": "sales", "from": start, "size": min(PAGE, per_query - start)}
            body = None
            for attempt in range(3):
                try:
                    r = s.get(URL, params=params, timeout=25)
                    if r.status_code == 200:
                        body = r.json()
                        break
                    log.warning("basalam %s HTTP %s", q, r.status_code)
                    if r.status_code == 403:
                        raise RuntimeError("باسلام درخواست را مسدود کرد (403)")
                except RuntimeError:
                    raise
                except Exception as e:  # noqa: BLE001
                    log.warning("basalam %s: %s", q, e)
                sleep(20 * (attempt + 1))
            rows = (body or {}).get("products") or []
            for p in rows:
                pos += 1
                c = card(p, q, pos)
                if c["id"] not in seen:
                    seen.add(c["id"])
                    out.append(c)
            if len(rows) < params["size"]:
                break
        if progress:
            progress(qi + 1, len(queries))
        log.info("basalam %s: %d so far", q, len(out))
    return out
