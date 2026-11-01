"""Etsy best-sellers through Apify (actor automation-lab/etsy-scraper: residential proxies, gets past
Etsy's DataDome). We start one run per search word on Apify's servers, wait, and read the results.
Nothing heavy runs on our VPS. The run has a hard dollar cap (APIFY_MAX_USD, split across the words).
"""
from __future__ import annotations

import logging
import time

import requests

from . import config as C

log = logging.getLogger(__name__)
API = "https://api.apify.com/v2"


def _num(x):
    try:
        return float(str(x).replace(",", ""))
    except (TypeError, ValueError):
        return None


def card(it: dict, query: str) -> dict:
    price = _num(it.get("price"))
    cur = (it.get("currency") or "USD").upper()
    tags = it.get("tags") or []
    mats = it.get("materials") or []
    return {
        "source": "etsy", "id": str(it.get("listingId") or ""), "title": it.get("name") or "",
        "url": it.get("url") or "", "image": it.get("imageUrl") or "",
        "price_usd": price if cur == "USD" else None,
        "price_toman": round(price * C.USD_TOMAN) if (price and cur == "USD") else None,
        "sales_total": _num(it.get("sellerSales")) or 0,           # shop's total sales
        "sales_week": None, "bought_24h": _num(it.get("boughtInLast24Hours")),
        "in_cart": _num(it.get("inCartCount")), "rating": _num(it.get("rating")),
        "reviews": _num(it.get("reviewCount")) or 0, "category": "", "shop": it.get("shop") or "",
        "shop_city": "", "query": query, "position": int(_num(it.get("position")) or 0),
        "tags": ", ".join(map(str, tags)) if isinstance(tags, list) else str(tags),
        "materials": ", ".join(map(str, mats)) if isinstance(mats, list) else str(mats),
    }


class Apify:
    def __init__(self, token: str):
        if not token:
            raise RuntimeError("کلید APIFY_TOKEN وارد نشده (در Coolify، بخش Environment)")
        self.s = requests.Session()
        self.s.headers["Authorization"] = f"Bearer {token}"

    def run(self, inp: dict, max_usd: float) -> dict:
        r = self.s.post(f"{API}/acts/{C.APIFY_ACTOR}/runs", json=inp,
                        params={"maxTotalChargeUsd": f"{max_usd:.2f}"}, timeout=60)
        r.raise_for_status()
        run = r.json()["data"]
        while run["status"] in ("READY", "RUNNING"):
            time.sleep(15)
            run = self.s.get(f"{API}/actor-runs/{run['id']}", timeout=60).json()["data"]
        return run

    def items(self, dataset_id: str) -> list[dict]:
        r = self.s.get(f"{API}/datasets/{dataset_id}/items", params={"clean": "true", "format": "json"}, timeout=120)
        r.raise_for_status()
        return r.json()

    def cost(self, run: dict) -> float:
        return float(run.get("usageTotalUsd") or (run.get("stats") or {}).get("totalCostUsd") or 0)


def fetch(token: str, queries: list[str] | None = None, per_query: int | None = None, progress=None,
          on_cost=None) -> list[dict]:
    queries = queries or C.ETSY_QUERIES
    per_query = per_query or C.ETSY_PER_QUERY
    ap = Apify(token)
    cap = C.APIFY_MAX_USD / len(queries)
    seen: set[str] = set()
    out: list[dict] = []
    for qi, q in enumerate(queries):
        inp = {"searchQuery": q, "maxItems": per_query, "sort": "most_relevant", "currency": "USD",
               "locale": "en-US", "excludeDigitalDownloads": True, "enrichListingDetails": C.ETSY_ENRICH,
               "proxyConfiguration": {"useApifyProxy": True, "apifyProxyGroups": ["RESIDENTIAL"]}}
        run = ap.run(inp, cap)
        if on_cost:
            on_cost(q, ap.cost(run), run.get("status"))
        if run["status"] != "SUCCEEDED":
            log.warning("etsy %s: run %s", q, run["status"])
        items = ap.items(run["defaultDatasetId"]) if run.get("defaultDatasetId") else []
        for it in items:
            c = card(it, q)
            if c["id"] and c["id"] not in seen and not it.get("isDigitalDownload"):
                seen.add(c["id"])
                out.append(c)
        if progress:
            progress(qi + 1, len(queries))
        log.info("etsy %s: %d items, %d total", q, len(items), len(out))
    return out
