"""The professional layer of the report.

Rule-based (numbers never come from the AI):
  economics  per test design: retail price, target price to pay the maker, test quantity, where to sell, risks
  markets    who buys on each market: top style / material / colour, median price, personalised share
  quadrants  demand x competition for the opportunity map

AI (one call): an executive analysis written only from those numbers: a one-line headline, findings,
this week's actions, risks and a short brief to read to the maker.
"""
from __future__ import annotations

import json
import logging
import re
import statistics

import requests

from . import analyze as A
from . import config as C

log = logging.getLogger(__name__)

# rule of thumb: pay the maker at most ~45% of the shelf price; the rest covers platform fee, packing,
# shipping, ads, returns and margin. Shown as an assumption, adjustable with BUY_SHARE.
BUY_SHARE = C.BUY_SHARE


def _r(x, step=10000):
    return int(round(x / step) * step) if x else None


def economics(o: dict, mid_week: float) -> dict:
    lo, hi, med = o.get("price_low"), o.get("price_high"), o.get("price_median")
    retail = med or ((lo + hi) / 2 if lo and hi else None)
    if retail and lo and hi and hi > 4 * lo:      # wide range: steel and silver mixed; aim at the cheaper half
        retail = (lo + retail) / 2
    week = o.get("week") or 0
    qty = 20 if week >= 50 else 12 if week >= 15 else 6
    channels = []
    if week >= mid_week:
        channels.append("باسلام")
    if o.get("dk_reviews", 0) >= 100 and o.get("dk_match", 99) <= 3:
        channels.append("دیجی‌کالا")
    if o.get("source") in ("etsy", "google") or not channels:
        channels.append("اینستاگرام و سایت خودتان")
    risks = []
    if week < 5:
        risks.append("فروش فعلی کم است؛ آزمایش با تعداد خیلی کم")
    if o.get("supply", 0) >= 2000:
        risks.append("رقیب زیاد در باسلام؛ باید با کیفیت یا عکس بهتر فرق کند")
    if o.get("dk_match", 0) >= 10:
        risks.append("دیجی‌کالا پر از همین طرح است")
    if lo and hi and hi > 4 * lo:
        risks.append("قیمت‌ها پراکنده‌اند (استیل و نقره قاطی)؛ جنس را اول مشخص کنید")
    if o.get("weak"):
        risks.append("پرفروش‌های فعلی امتیاز پایین دارند؛ کیفیت ساخت مهم است")
    return {"retail": _r(retail), "buy_max": _r(retail * BUY_SHARE) if retail else None, "test_qty": qty,
            "channels": channels, "risks": risks}


def mid_week(opps: list[dict]) -> float:
    w = sorted(o.get("week", 0) for o in opps) or [0]
    return max(3, w[len(w) // 2])


def markets(etsy: list[dict], bas: list[dict], dk: list[dict]) -> list[dict]:
    out = []
    for key, name, items in (("etsy", "اتسی", etsy), ("basalam", "باسلام", bas), ("digikala", "دیجی‌کالا", dk)):
        if not items:
            continue

        def top(field, n=2):
            c = {}
            for x in items:
                v = x.get(field) or "سایر"
                if v != "سایر":
                    c[v] = c.get(v, 0) + 1
            return [(k, round(v * 100 / len(items))) for k, v in sorted(c.items(), key=lambda kv: -kv[1])[:n]]

        price_key = "price_usd" if key == "etsy" else "price_toman"
        neck = [x[price_key] for x in items if x.get("type") == "گردنبند" and x.get(price_key)]
        allp = [x[price_key] for x in items if x.get(price_key)]
        out.append({"key": key, "name": name, "n": len(items), "style": top("style"), "material": top("material"),
                    "color": top("color"),
                    "price_median": statistics.median(neck or allp) if (neck or allp) else None,
                    "price_of": "گردنبند" if neck else "همه",
                    "personal": round(100 * sum(1 for x in items if x.get("personalized")) / len(items))})
    return out


ASK = """تو یک تحلیلگر ارشد بازار جواهرات دست‌ساز در ایران هستی و برای صاحب یک کسب‌وکار کوچک می‌نویسی که
با تولیدکننده‌های ایرانی کار می‌کند و روش Shein را در مقیاس کوچک اجرا می‌کند (از هر طرح چند عدد بساز، فروش را بسنج،
برنده‌ها را دوباره سفارش بده). داده‌ی زیر از پرفروش‌های اتسی (جهانی)، باسلام و دیجی‌کالا (ایران) و گوگل ترندز ایران است.

قواعد:
- فقط از عددهای همین داده استفاده کن؛ هیچ عددی از خودت نساز. اگر چیزی در داده نیست، درباره‌اش ادعا نکن.
- فارسی ساده، جمله‌های کوتاه، بدون اصطلاح فنی و بدون تعارف.
- طرح‌های برندها (ونکلیف، تیفانی و…) را پیشنهاد نکن.
- عددهایی که اسمشان با _pct تمام می‌شود درصدند (مثلاً «۳۶٪ پرفروش‌های اتسی»)، نه تعداد.
- maker_brief را خطاب به تولیدکننده بنویس و فقط درباره‌ی ساختن: کدام طرح‌ها، جنس، رنگ، اندازه، چند عدد نمونه، و اینکه
  قیمت و زمان تحویلش را بگوید. سقف قیمت خرید ما (buy_max)، قیمت فروش ما و برنامه‌ی فروش را هرگز در آن ننویس.

فقط JSON بده:
{"headline": "یک جمله: مهم‌ترین نتیجه‌ی این هفته",
 "findings": [{"title": "۳ تا ۶ کلمه", "text": "۱ تا ۲ جمله با عدد"}],   // ۴ تا ۵ مورد
 "actions": ["کار مشخص این هفته"],                                       // ۳ تا ۵ مورد، به ترتیب اهمیت
 "risks": ["ریسک یا محدودیت داده"],                                        // ۲ تا ۴ مورد
 "maker_brief": "یک پاراگراف کوتاه که صاحب کسب‌وکار عیناً برای تولیدکننده بخواند"}
داده:
"""


def executive(st: dict, tl: list[dict], tr: list[dict], mk: list[dict], key: str) -> tuple[dict, float]:
    if not key:
        return {}, 0.0
    data = {
        "markets": [{**{k: v for k, v in m.items() if k not in ("style", "material", "color", "personal")},
                     "top_style_pct": m["style"], "top_material_pct": m["material"], "top_color_pct": m["color"],
                     "personalised_pct": m["personal"]} for m in mk],
        "style_share": [{"name": r["name"], "etsy_pct": round(r["etsy"]), "basalam_pct": round(r["basalam"]),
                         "digikala_pct": round(r.get("digikala", 0))} for r in st.get("style", [])][:8],
        "material_share": [{"name": r["name"], "etsy_pct": round(r["etsy"]), "basalam_pct": round(r["basalam"]),
                            "digikala_pct": round(r.get("digikala", 0))} for r in st.get("material", [])][:8],
        "test_list": [{"design": o.get("name"), "search": o["q"], "labels": o["labels"],
                       "basalam_sales_this_week_top10": o["week"], "basalam_products": o["supply"],
                       "digikala_same_design_in_top20": o.get("dk_match"),
                       "digikala_ratings": o.get("dk_reviews"), **{k: o["eco"][k] for k in
                       ("retail", "buy_max", "test_qty", "channels")}} for o in tl],
        "google_trends": [{"keyword": r["keyword"], "yoy_pct": round(r["yoy"]) if r.get("yoy") is not None else None, "peak_months": r.get("peak_months"),
                           "rising": [q["query"] for q in (r.get("breakout", []) + r.get("rising", []))[:3]]}
                          for r in tr if r.get("average")][:15],
    }
    body = {"model": C.ANALYST_MODEL, "max_tokens": 4000, "temperature": 0.3, "reasoning": {"enabled": False},
            "messages": [{"role": "user", "content": ASK + json.dumps(data, ensure_ascii=False, default=round)}]}
    try:
        r = requests.post(A.OPENROUTER, json=body, timeout=180, headers={
            "Authorization": f"Bearer {key}", "Content-Type": "application/json", "X-Title": "Dastsaz trends"})
        j = r.json()
        txt = ((j.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
        m = re.search(r"\{.*\}", txt, re.S)
        out = json.loads(m.group(0)) if m else {}
        clean = {"headline": str(out.get("headline") or ""),
                 "findings": [{"title": str(f.get("title") or ""), "text": str(f.get("text") or "")}
                              for f in out.get("findings") or [] if isinstance(f, dict)][:6],
                 "actions": [str(a) for a in out.get("actions") or []][:6],
                 "risks": [str(a) for a in out.get("risks") or []][:5],
                 "maker_brief": str(out.get("maker_brief") or "")}
        return clean, float((j.get("usage") or {}).get("cost") or 0)
    except Exception as e:  # noqa: BLE001
        log.warning("executive analysis failed: %s", e)
        return {}, 0.0
