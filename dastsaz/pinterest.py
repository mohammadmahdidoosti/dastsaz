"""Weekly Pinterest reading through Apify (actor logiover/pinterest-scraper, a paid hosted service; we never call
Pinterest's own search ourselves). About $1.4 per 1000 pins: 10 words x 50 pins ~ $0.70 a week.

Per pin we get the picture, title, description, dominant colour, reactions (hearts, about half the pins), the
date it was posted and where it links to. No save counts (Pinterest search does not give them).
Score = hearts per month of age + this week's new hearts + small bonuses for linking to a shop, being fresh
and ranking high in the search. The supplier can mark pins he likes on his page; those go to the design machine.
"""
from __future__ import annotations

import datetime as dt
import email.utils
import hashlib
import json
import logging
import math
import threading
from pathlib import Path
from urllib.parse import urlparse

import requests

from . import config as C

log = logging.getLogger(__name__)
ACTOR = "logiover~pinterest-scraper"
TERMS = ["clay earrings", "polymer clay necklace", "handmade silver earrings", "whimsical jewelry", "fruit earrings",
         "handmade beaded necklace", "dainty charm bracelet", "enamel ring", "mushroom jewelry", "cute handmade ring"]
SHOPS = ("etsy.", "depop.", "shopify", "myshopify", "amazon.", "ebay.", "instagram.com", "bigcartel", "storenvy",
         "aliexpress", "temu.", "shein.")
_lock = threading.Lock()


def _dir() -> Path:
    d = C.DATA_DIR / "pinterest"
    (d / "img").mkdir(parents=True, exist_ok=True)
    return d


def _date(s) -> str:
    try:
        return email.utils.parsedate_to_datetime(str(s)).date().isoformat()
    except (TypeError, ValueError):
        try:
            return dt.date.fromisoformat(str(s)[:10]).isoformat()
        except ValueError:
            return ""


def _int(x) -> int | None:
    try:
        return int(float(x))
    except (TypeError, ValueError):
        return None


def card(it: dict, pos: int) -> dict:
    link = str(it.get("link") or "")
    host = urlparse(link).netloc.lower().removeprefix("www.")
    board = it.get("board") if isinstance(it.get("board"), dict) else {}
    pinner = it.get("pinner") if isinstance(it.get("pinner"), dict) else {}
    return {"id": str(it.get("id") or ""), "title": str(it.get("title") or "")[:200],
            "desc": str(it.get("description") or "")[:400], "image": str(it.get("imageUrl") or ""),
            "url": str(it.get("pinUrl") or ""), "link": link, "host": host,
            "shop": any(s in host for s in SHOPS), "color": str(it.get("dominantColor") or ""),
            "react": _int(it.get("reactionCount")), "created": _date(it.get("createdAt")),
            "term": str(it.get("fromSearch") or ""), "pos": pos, "video": str(it.get("isVideo")) == "True",
            "board": str(board.get("name") or "")[:80], "pinner": str(pinner.get("username") or "")[:60]}


def score(p: dict, prev: dict | None, today: dt.date) -> float:
    try:
        age = max(7, (today - dt.date.fromisoformat(p["created"])).days)
    except (KeyError, ValueError):
        age = 365
    r = p.get("react") or 0
    s = math.log1p(r * 30 / age) * 1.0                     # hearts per month of age
    if prev and prev.get("react") is not None and p.get("react") is not None:
        s += math.log1p(max(0, r - prev["react"])) * 1.5    # new hearts since last week
    s += 1.0 if p.get("shop") else 0.0                      # liked AND someone sells it
    s += 0.5 if age <= 90 else 0.0
    s += max(0.0, (50 - p.get("pos", 50)) / 50) * 0.5       # Pinterest shows popular pins higher
    return round(s, 3)


def history() -> list[Path]:
    return sorted(_dir().glob("20*.json"))


def latest() -> dict | None:
    h = history()
    return json.loads(h[-1].read_text(encoding="utf-8")) if h else None


def _thumb(url: str, pid: str, sess) -> str:
    """A small copy on our server: Pinterest's picture host may not open on every phone in Iran."""
    name = hashlib.sha1(pid.encode()).hexdigest()[:12] + ".jpg"
    f = _dir() / "img" / name
    if f.exists():
        return name
    try:
        r = sess.get(url, timeout=30)
        if r.status_code == 200 and r.content:
            from .designs import shrink
            f.write_bytes(shrink(r.content, 500))
            return name
    except requests.RequestException as e:
        log.info("pin picture %s: %s", pid, e)
    return ""


def run(terms: list[str] | None = None, per: int = 50, max_usd: float = 1.0, ap=None, top: int = 60,
        sess=None) -> dict:
    from .etsy import Apify
    terms = terms or TERMS
    ap = ap or Apify(C.secret("APIFY_TOKEN"))
    r = ap.run({"searchTerms": terms, "maxItemsPerInput": per, "maxResults": per * len(terms)}, max_usd, actor=ACTOR)
    items = ap.items(r["defaultDatasetId"]) if r.get("defaultDatasetId") else []
    pos: dict[str, int] = {}
    pins: dict[str, dict] = {}
    for it in items:
        t = str(it.get("fromSearch") or "")
        pos[t] = pos.get(t, 0) + 1
        p = card(it, pos[t])
        if p["id"] and p["id"] not in pins and not p["video"]:
            pins[p["id"]] = p
    old = latest()
    prev = {p["id"]: p for p in (old or {}).get("pins", [])}
    today = C.today()
    for p in pins.values():
        p["score"] = score(p, prev.get(p["id"]), today)
        if p["id"] in prev:
            p["first"] = prev[p["id"]].get("first") or old["date"]
            p["liked"] = prev[p["id"]].get("liked", False)
        else:
            p["first"] = today.isoformat()
    ranked = sorted(pins.values(), key=lambda p: -p["score"])
    sess = sess or requests.Session()
    for p in ranked[:top]:
        p["thumb"] = _thumb(p["image"], p["id"], sess) if p["image"] else ""
    # pins the supplier liked last week stay, even if this week's search did not return them
    for pid, p in prev.items():
        if p.get("liked") and pid not in pins:
            ranked.append(p)
    out = {"date": today.isoformat(), "terms": terms, "usd": round(ap.cost(r), 3), "n": len(items), "pins": ranked}
    (_dir() / f"{today.isoformat()}.json").write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    log.info("pinterest: %d pins, $%.3f", len(ranked), out["usd"])
    return {k: out[k] for k in ("date", "usd", "n")}


def like(pid: str, on: bool) -> bool:
    with _lock:
        h = history()
        if not h:
            return False
        d = json.loads(h[-1].read_text(encoding="utf-8"))
        hit = False
        for p in d["pins"]:
            if p["id"] == pid:
                p["liked"] = on
                hit = True
        if hit:
            h[-1].write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
        return hit


def for_designs(n: int = 20) -> list[str]:
    """Short texts of the pins the supplier liked first, then the hottest, for the design machine (taste, not copy)."""
    d = latest()
    if not d:
        return []
    pins = sorted(d["pins"], key=lambda p: (not p.get("liked"), -p.get("score", 0)))
    out = []
    for p in pins[:n]:
        t = (p.get("title") or "").strip()
        if p.get("desc"):
            t = (t + ": " if t else "") + p["desc"][:160]
        if t:
            out.append(("[سازنده پسندید] " if p.get("liked") else "") + t)
    return out
