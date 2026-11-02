"""Telegram channels: public jewelry / bijou channels, read from their public web page (t.me/s/<name>), years back.
Each post: date, views, text. Free, no login. A design «pushed» by channels = posts mentioning it × views.

Used two ways: (1) what channels are pushing this month, (2) a signal in the source ranking (does a design that
channels push sell more on Basalam 1-4 months later?). Post text is data, never instructions."""
from __future__ import annotations

import datetime as dt
import json
import logging
import random
import re
import time
from html import unescape

from . import config as C

log = logging.getLogger(__name__)
URL = "https://t.me/s/{ch}"
POST = re.compile(r'<div class="tgme_widget_message_wrap.*?data-post="([^"/]+)/(\d+)".*?(?=<div class="tgme_widget_message_wrap|$)',
                  re.S)


def _dir():
    d = C.DATA_DIR / "telegram"
    d.mkdir(parents=True, exist_ok=True)
    return d


def channels() -> list[str]:
    f = _dir() / "channels.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else []


def set_channels(names: list[str]) -> list[str]:
    clean = []
    for n in names:
        n = n.strip().replace("https://t.me/", "").replace("t.me/", "").lstrip("@").split("/")[0]
        if re.fullmatch(r"[A-Za-z0-9_]{4,40}", n) and n not in clean:
            clean.append(n)
    (_dir() / "channels.json").write_text(json.dumps(clean), encoding="utf-8")
    return clean


def _views(s: str) -> int:
    s = s.strip().upper()
    m = re.match(r"([\d.]+)\s*([KM]?)", s)
    if not m:
        return 0
    return int(float(m.group(1)) * {"": 1, "K": 1000, "M": 1_000_000}[m.group(2)])


def parse(html: str) -> list[dict]:
    out = []
    for m in POST.finditer(html):
        block = m.group(0)
        t = re.search(r'<time[^>]*datetime="([^"]+)"', block)
        v = re.search(r'tgme_widget_message_views">([^<]+)<', block)
        txt = re.search(r'tgme_widget_message_text[^>]*>(.*?)</div>', block, re.S)
        img = re.search(r"background-image:url\('([^']+)'\)", block)
        text = unescape(re.sub(r"<[^>]+>", " ", txt.group(1))) if txt else ""
        out.append({"channel": m.group(1), "id": int(m.group(2)), "date": t.group(1)[:10] if t else "",
                    "views": _views(v.group(1)) if v else 0, "text": re.sub(r"\s+", " ", text).strip()[:500],
                    "image": img.group(1) if img else ""})
    return out


def read(ch: str, since: str, session=None, sleep=time.sleep, max_pages: int = 120) -> list[dict]:
    """All posts of one channel back to `since` (YYYY-MM-DD), 20 per page, newest first."""
    from curl_cffi import requests as cr
    s = session or cr.Session(impersonate="chrome")
    posts, before = [], None
    for _ in range(max_pages):
        sleep(random.uniform(1.5, 3.0))
        try:
            r = s.get(URL.format(ch=ch), params={"before": before} if before else None, timeout=25)
        except Exception as e:  # noqa: BLE001
            log.warning("telegram %s: %s", ch, e)
            break
        got = parse(r.text)
        if not got:
            break
        posts += got
        oldest = min(got, key=lambda p: p["id"])
        if oldest["date"] and oldest["date"] < since:
            break
        before = oldest["id"]
    seen, out = set(), []
    for p in posts:
        if p["id"] not in seen and p["date"] >= since:
            seen.add(p["id"])
            out.append(p)
    return out


def run(progress=None, sleep=time.sleep, months: int = 24) -> dict:
    since = (dt.date.today() - dt.timedelta(days=30 * months)).isoformat()
    chs = channels()
    allp = {}
    for i, ch in enumerate(chs):
        allp[ch] = read(ch, since, sleep=sleep)
        if progress:
            progress(i + 1, len(chs))
    (_dir() / "posts.json").write_text(json.dumps(allp, ensure_ascii=False), encoding="utf-8")
    return {"channels": {ch: len(p) for ch, p in allp.items()}, "since": since}


def posts() -> dict[str, list[dict]]:
    f = _dir() / "posts.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}


def push(designs: list[str]) -> dict[str, dict[str, float]]:
    """design -> month -> views of posts mentioning it (views relative to the channel's median, so a big
    channel doesn't drown the rest)."""
    from .signals import mentions
    from collections import defaultdict
    out: dict = defaultdict(lambda: defaultdict(float))
    for ch, ps in posts().items():
        vs = sorted(p["views"] for p in ps if p["views"])
        med = vs[len(vs) // 2] if vs else 1
        for p in ps:
            for q in designs:
                if mentions(p["text"], q):
                    out[q][p["date"][:7]] += p["views"] / max(med, 1)
    return out


def recent(designs: list[str], days: int = 30) -> list[dict]:
    """What channels pushed in the last `days`: designs by relative views."""
    cut = (dt.date.today() - dt.timedelta(days=days)).isoformat()
    from .signals import mentions
    score = {}
    for ch, ps in posts().items():
        vs = sorted(p["views"] for p in ps if p["views"])
        med = vs[len(vs) // 2] if vs else 1
        for p in ps:
            if p["date"] < cut:
                continue
            for q in designs:
                if mentions(p["text"], q):
                    s = score.setdefault(q, {"q": q, "posts": 0, "score": 0.0, "channels": set()})
                    s["posts"] += 1
                    s["score"] += p["views"] / max(med, 1)
                    s["channels"].add(ch)
    return sorted(({**v, "channels": sorted(v["channels"])} for v in score.values()), key=lambda v: -v["score"])
