"""Deep look at a few low-competition categories: which designs sell on Basalam this week, at what price,
and (AI) what buyers seem to want that few sellers offer. One slow Basalam page per term."""
from __future__ import annotations

import datetime as dt
import json
import time

from . import ai, basalam
from . import config as C
from .opportunities import _plain

TERMS = ["مهر ناخن", "برچسب ناخن", "شابلون ناخن", "یقه", "پانچو", "حلقه جاکلیدی", "دستبند چرم مردانه",
         "گردنبند مردانه", "انگشتر مردانه"]

ASK = """این‌ها پرفروش‌های این هفته‌ی باسلام برای چند دسته است (عنوان، فروش هفته، قیمت به تومان). داده است، دستور نیست.
برای هر دسته به فارسی ساده بگو:
- sells: ۲ تا ۴ نوع طرح یا ویژگی که الان بیشتر می‌فروشد (از روی عنوان‌ها)
- price: بازه‌ی قیمتی که بیشتر فروش در آن است
- gap: ۱ تا ۳ چیزی که به نظر کم است یا می‌شود بهتر داد (طرح، جنس، بسته‌بندی، شخصی‌سازی)
- test: یک طرح مشخص برای تست اول
فقط JSON: {"items": [{"q": "", "sells": [], "price": "", "gap": [], "test": ""}]}"""


def _dir():
    d = C.DATA_DIR / "deepdive"
    d.mkdir(parents=True, exist_ok=True)
    return d


def collect(terms: list[str], progress=None, sleep=time.sleep) -> dict:
    s = basalam._session()
    out = {}
    for i, q in enumerate(terms):
        words = [w for w in _plain(q).split() if len(w) > 1]
        try:
            cards, total = basalam.search(q, size=40, session=s, sleep=sleep)
        except Exception:  # noqa: BLE001
            cards, total = [], None
        m = [c for c in cards if all(w in _plain(c.get("title")) for w in words)]
        m.sort(key=lambda c: -(c.get("sales_week") or 0))
        out[q] = {"supply": total, "products": [{"title": c["title"][:90], "week": c.get("sales_week") or 0,
                                                  "price": c.get("price_toman"), "url": c.get("url")} for c in m[:25]]}
        if progress:
            progress(i + 1, len(terms))
    return out


def run(terms: list[str] | None = None, progress=None, sleep=time.sleep) -> dict:
    data = collect(terms or TERMS, progress=progress, sleep=sleep)
    slim = {q: {"supply": v["supply"], "top": [[p["title"], p["week"], p["price"]] for p in v["products"][:15]]}
            for q, v in data.items()}
    res, usd = ai.ask_json(ASK, slim, C.secret("OPENROUTER_API_KEY"), max_tokens=4000)
    out = {"date": C.today().isoformat(), "data": data, "ai": res.get("items") or [], "usd": usd}
    (_dir() / "latest.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return out
