"""One AI call per product (photo + title + tags): Persian name and its type, style, material, colour,
chosen from fixed Persian lists so the report can count them. Model through OpenRouter, real cost recorded."""
from __future__ import annotations

import json
import logging
import math
import re
import time
from concurrent.futures import ThreadPoolExecutor

import requests

from . import config as C

log = logging.getLogger(__name__)
OPENROUTER = "https://openrouter.ai/api/v1/chat/completions"

TYPES = ["گردنبند", "گوشواره", "انگشتر", "دستبند", "پابند", "سنجاق سینه", "آویز", "ست", "النگو", "سایر"]
STYLES = ["مینیمال", "بوهو", "وینتیج", "کلاسیک و لوکس", "اسم و حروف", "گل و طبیعت", "سنتی و قومی",
          "مدرن هندسی", "فانتزی و بامزه", "معنوی و نمادین", "سایر"]
MATERIALS = ["نقره", "طلا", "روکش طلا", "استیل", "برنج و مس", "سنگ طبیعی", "مروارید", "رزین", "چوب",
             "چرم", "مهره و منجوق", "پارچه و نخ", "بدلیجات", "سایر"]
COLORS = ["طلایی", "نقره‌ای", "رزگلد", "سفید", "مشکی", "سبز", "آبی", "قرمز", "صورتی", "بنفش", "چندرنگ", "سایر"]

ASK = """You classify jewelry listings for a Persian trend report.
Source: {source}. Title: {title}
Tags: {tags}
Materials given by seller: {seller_materials}
Look at the photo (if any) and the text. Answer JSON only:
{{"name_fa": "short natural Persian product name (max 8 words, translate if English)",
 "is_jewelry": true/false (wearable jewelry or jewelry set; false for boxes, tools, supplies, beads for making, ads),
 "type": one of {types},
 "style": one of {styles},
 "material": one of {materials} (main visible/declared material),
 "color": one of {colors} (main colour of the piece),
 "personalized": true/false (name, initials, birthstone, custom engraving),
 "motif": "main motif in 1-3 Persian words, e.g. قلب، ماه، پروانه، حرف لاتین",
 "stone": "stone or bead type in Persian, or empty"}}"""


def _pick(v, allowed):
    v = str(v or "").strip()
    return v if v in allowed else "سایر"


def classify(p: dict, key: str, session=None, model: str | None = None) -> dict:
    s = session or requests
    text = ASK.format(source=p["source"], title=p["title"][:300], tags=(p.get("tags") or "")[:300],
                      seller_materials=(p.get("materials") or "")[:200], types=TYPES, styles=STYLES,
                      materials=MATERIALS, colors=COLORS)
    content = [{"type": "text", "text": text}]
    if p.get("image"):
        content.append({"type": "image_url", "image_url": {"url": p["image"]}})
    body = {"model": model or C.AI_MODEL, "max_tokens": 400, "temperature": 0,
            "reasoning": {"enabled": False}, "messages": [{"role": "user", "content": content}]}
    err = ""
    for attempt in range(3):
        try:
            r = s.post(OPENROUTER, json=body, timeout=90, headers={
                "Authorization": f"Bearer {key}", "Content-Type": "application/json",
                "HTTP-Referer": "https://dastsaz.caravansanat.com", "X-Title": "Dastsaz trends"})
        except requests.RequestException as e:
            err = str(e)
            time.sleep(3)
            continue
        if r.status_code != 200:
            err = f"HTTP {r.status_code}: {r.text[:150]}"
            if "Reasoning is mandatory" in r.text:
                body.pop("reasoning", None)
                body["max_tokens"] = 2000
            elif "image" in r.text.lower() and len(content) > 1:   # photo not readable: text only
                content.pop()
            time.sleep(3)
            continue
        j = r.json()
        txt = ((j.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
        m = re.search(r"\{.*\}", txt, re.S)
        try:
            out = json.loads(m.group(0)) if m else {}
        except ValueError:
            out = {}
        if not out:
            err = "unparsable: " + txt[:100]
            continue
        return {"name_fa": str(out.get("name_fa") or "")[:80], "is_jewelry": out.get("is_jewelry") is not False,
                "type": _pick(out.get("type"), TYPES), "style": _pick(out.get("style"), STYLES),
                "material": _pick(out.get("material"), MATERIALS), "color": _pick(out.get("color"), COLORS),
                "personalized": out.get("personalized") is True, "motif": str(out.get("motif") or "")[:30],
                "stone": str(out.get("stone") or "")[:30],
                "_cost": float((j.get("usage") or {}).get("cost") or 0), "_error": ""}
    return {"name_fa": "", "is_jewelry": True, "type": "سایر", "style": "سایر", "material": "سایر",
            "color": "سایر", "personalized": False, "motif": "", "stone": "", "_cost": 0.0, "_error": err}


def classify_all(items: list[dict], key: str, progress=None) -> tuple[list[dict], float]:
    if not key:
        raise RuntimeError("کلید OPENROUTER_API_KEY وارد نشده (در Coolify، بخش Environment)")
    done = [0]
    sess = requests.Session()

    def one(p):
        res = classify(p, key, sess)
        done[0] += 1
        if progress and done[0] % 10 == 0:
            progress(done[0], len(items))
        return {**p, **res}

    with ThreadPoolExecutor(C.AI_WORKERS) as ex:
        out = list(ex.map(one, items))
    return out, round(sum(x["_cost"] for x in out), 4)


def popularity(p: dict) -> float:
    """Etsy: bought in 24h and in carts when known, then reviews and Etsy's own order (it puts best-sellers
    first). Basalam: sales this week, then total. Digikala: its best-seller order, then number of ratings."""
    pos = p.get("position") or 99
    if p["source"] == "digikala":     # no sales count: its best-seller order, then number of ratings
        return max(0, 60 - (p.get("position") or 60)) * 2 + math.log1p(p.get("reviews") or 0) * 5
    if p["source"] == "etsy":
        return ((p.get("bought_24h") or 0) * 100 + (p.get("in_cart") or 0) * 5
                + math.log1p(p.get("reviews") or 0) * 3 + max(0, 60 - pos) * 0.15)
    return (p.get("sales_week") or 0) * 100 + (p.get("sales_total") or 0) + math.log1p(p.get("reviews") or 0)


def top(items: list[dict], n: int) -> list[dict]:
    return sorted(items, key=popularity, reverse=True)[:n]
