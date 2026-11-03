"""Today's silver and gold price per gram in Iran (tgju.org public price feed, rial -> toman).

Used to check a silver design's purchase ceiling: if the ceiling barely covers the silver itself, a silver
version is not possible at that price (steel or plated then)."""
from __future__ import annotations

import logging

log = logging.getLogger(__name__)
URL = "https://call1.tgju.org/ajax.json"
KEYS = {"silver_925": "نقره ۹۲۵ (هر گرم)", "silver_999": "نقره ۹۹۹ (هر گرم)", "geram18": "طلای ۱۸ عیار (هر گرم)",
        "price_dollar_rl": "دلار (بازار آزاد)"}


def _num(s) -> float | None:
    try:
        return float(str(s).replace(",", ""))
    except (TypeError, ValueError):
        return None


def fetch(session=None) -> dict:
    """{key: {'name', 'toman', 'time'}}; {} if the feed can't be read."""
    try:
        if session is None:
            from curl_cffi import requests as cr
            session = cr.Session(impersonate="chrome")
        cur = (session.get(URL, timeout=20).json() or {}).get("current") or {}
    except Exception as e:  # noqa: BLE001
        log.warning("metal prices: %s", e)
        return {}
    out = {}
    for k, name in KEYS.items():
        rial = _num((cur.get(k) or {}).get("p"))
        if rial:
            out[k] = {"name": name, "toman": round(rial / 10), "time": (cur.get(k) or {}).get("ts", "")}
    return out


def silver_note(o: dict, buy_max: float | None, prices: dict) -> str:
    """For a silver search: what the silver alone costs for a light piece, against our ceiling."""
    if "نقره" not in o.get("q", "") or not buy_max or "silver_925" not in prices:
        return ""
    g = prices["silver_925"]["toman"]
    grams = 3 if any(t in o["q"] for t in ("گردنبند", "دستبند")) else 2
    metal = g * grams
    if metal >= buy_max * 0.7:
        return (f"فقط نقره‌ی یک قطعه‌ی حدود {grams} گرمی امروز حدود {round(metal, -3):,.0f} تومان است؛ با این سقف خرید، "
                f"نسخه‌ی نقره‌ی واقعی ممکن نیست (استیل یا روکش)")
    return f"نقره‌ی یک قطعه‌ی حدود {grams} گرمی امروز حدود {round(metal, -3):,.0f} تومان است"


def record(prices: dict) -> None:
    """Keep one line a day (dollar, gold, silver) so their effect on what sells can be tested later."""
    import datetime as dt
    import json
    from . import config as C
    if not prices:
        return
    d = C.DATA_DIR / "macro"
    d.mkdir(parents=True, exist_ok=True)
    f = d / "daily.jsonl"
    today = C.today().isoformat()
    lines = [x for x in (f.read_text(encoding="utf-8").splitlines() if f.exists() else []) if not x.startswith('{"date": "' + today)]
    lines.append(json.dumps({"date": today, **{k: v["toman"] for k, v in prices.items()}}))
    f.write_text("\n".join(lines) + "\n", encoding="utf-8")
