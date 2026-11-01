"""Possible makers: Basalam booths among the jewelry best-sellers, with city, province and whether they look like a
workshop / home business that makes its own pieces (booth type and description), not a reseller of imports.
Read slowly from Basalam's public booth page data (core.basalam.com/api_v2/vendor/identifier/<id>)."""
from __future__ import annotations

import logging
import random
import re
import time
from collections import Counter, defaultdict

from . import basalam
from . import config as C

log = logging.getLogger(__name__)
URL = "https://core.basalam.com/api_v2/vendor/identifier/{id}"
MAKES = re.compile(r"دست\s*‌?\s*ساز|دستساز|کارگاه|طراحی و ساخت|ساخت خودم|ساخته شده توسط|سازنده|نقره\s*کار|"
                   r"زیورساز|جواهرساز|میناکاری|ملیله|سفال|رزین|مکرومه", re.I)
RESELL = re.compile(r"وارداتی|واردات|عمده|چین|ترکیه|پخش|حراجی", re.I)


def shops(bas_raw: list[dict], n: int = 40) -> list[dict]:
    g = defaultdict(lambda: {"products": 0, "sales": 0, "week": 0})
    for p in bas_raw:
        sid = p.get("shop_id")
        if not sid:
            continue
        s = g[sid]
        s.update({"id": sid, "name": p.get("shop") or sid, "owner_city": p.get("shop_city") or ""})
        s["products"] += 1
        s["sales"] += int(p.get("sales_total") or 0)
        s["week"] += int(p.get("sales_week") or 0)
    return sorted(g.values(), key=lambda s: -(s["sales"] + 20 * s["week"]))[:n]


def details(top: list[dict], progress=None, sleep=time.sleep) -> list[dict]:
    s = basalam._session()
    out = []
    for i, sh in enumerate(top):
        sleep(random.uniform(*C.BASALAM_DELAY))
        try:
            v = s.get(URL.format(id=sh["id"]), timeout=20).json()
        except Exception as e:  # noqa: BLE001
            log.warning("vendor %s: %s", sh["id"], e)
            v = {}
        city = v.get("city") or {}
        types = [c.get("title", "") for c in v.get("category_type") or []]
        text = " ".join([v.get("title") or "", v.get("description") or "", v.get("summary") or ""])
        out.append({**sh, "name": v.get("title") or sh["name"], "city": city.get("title") or sh.get("owner_city", ""),
                    "province": (city.get("parent") or {}).get("title") or "", "types": types,
                    "since": (v.get("created_at") or "")[:4], "catalog": v.get("product_count"),
                    "maker": bool(MAKES.search(text)) and not RESELL.search(text),
                    "url": f"https://basalam.com/{sh['id']}"})
        if progress:
            progress(i + 1, len(top))
    return sorted(out, key=lambda m: (not m["maker"], -(m["sales"] + 20 * m["week"])))


def by_province(makers: list[dict]) -> list[tuple[str, int]]:
    return Counter(m["province"] for m in makers if m["maker"] and m["province"]).most_common(10)
