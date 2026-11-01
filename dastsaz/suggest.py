"""What Iranians type: Digikala's search suggestions (api.digikala.com/v1/autocomplete). For each jewelry word and
the word plus a starting letter, Digikala suggests ~6 completions. A completion that comes back for many prefixes
is typed often. Jewelry completions we do not search yet become extra opportunity searches.

(Basalam shows suggestions too, but loads them in a way we could not read from the server yet.)
"""
from __future__ import annotations

import logging
import random
import time
from collections import Counter

from . import digikala
from .trends import BRANDS, JEWELRY, NOT_DESIGN

log = logging.getLogger(__name__)
URL = "https://api.digikala.com/v1/autocomplete/"
TYPES = ["گردنبند", "گوشواره", "دستبند", "انگشتر", "پابند", "آویز", "ست زیورآلات", "زیورآلات دست ساز"]
LETTERS = ["ا", "ب", "ت", "ح", "د", "ر", "س", "ط", "گ", "م"]
DELAY = (2.0, 4.0)


def prefixes() -> list[str]:
    return TYPES + [f"{t} {l}" for t in TYPES[:4] for l in LETTERS]


def fetch(progress=None, session=None, sleep=time.sleep) -> dict:
    """{'counts': {keyword: how many prefixes suggested it}, 'trending': [Digikala-wide trending searches]}"""
    s = session or digikala._session()
    counts: Counter = Counter()
    trending: list[str] = []
    pre = prefixes()
    for i, p in enumerate(pre):
        sleep(random.uniform(*DELAY))
        try:
            r = s.get(URL, params={"q": p}, timeout=20)
            data = (r.json() or {}).get("data") or {} if r.status_code == 200 else {}
        except Exception as e:  # noqa: BLE001
            log.warning("autocomplete %s: %s", p, e)
            data = {}
        for k in ("auto_complete", "categories", "advance_links"):
            for x in data.get(k) or []:
                kw = str((x or {}).get("keyword") or "").strip()
                if kw:
                    counts[kw] += 1
        for x in data.get("trends") or []:
            kw = str((x or {}).get("keyword") or "").strip()
            if kw and kw not in trending:
                trending.append(kw)
        if progress:
            progress(i + 1, len(pre))
    return {"counts": dict(counts.most_common()), "trending": trending[:20]}


def ideas(sug: dict, known: set[str], n: int = 20) -> list[str]:
    """Typed-often jewelry searches that are a design (not a bare type, question, price or brand)."""
    out = []
    bare = set(TYPES) | {"گردنبند زنانه", "گوشواره زنانه", "دستبند زنانه", "انگشتر زنانه", "زیورآلات"}
    for kw, c in sorted((sug or {}).get("counts", {}).items(), key=lambda kv: -kv[1]):
        if (kw in known or kw in bare or kw in out or not JEWELRY.search(kw) or NOT_DESIGN.search(kw)
                or BRANDS.search(kw) or len(kw.split()) > 4 or len(kw) > 35):
            continue
        out.append(kw)
        if len(out) >= n:
            break
    return out
