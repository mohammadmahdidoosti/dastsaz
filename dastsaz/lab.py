"""The test lab: the ledger of experiments (the machine's memory), the scale (win / keep testing / drop) and how
much exposure each live test should get next.

A test = one design shown in one channel (Basalam booth, Instagram page, Telegram, ...) at one price.
Numbers are cumulative (total views so far, total messages so far, ...), entered by hand or later by a connector.

Interest = messages + add-to-carts + orders (pre-orders count as orders). Saves are kept but count for less.
Every round should have a control: a design we already know sells average. Each test is judged against the
control in the same channel, so the day, the season and the channel's mood cancel out.

Decision rule (fixed BEFORE the test, so we don't fool ourselves):
- under MIN_VIEWS views: too early
- interest rate >= max(WIN_ABS, WIN_X * control rate): winner -> small buy / reorder
- after 2 * MIN_VIEWS views, rate < DROP_X * control rate: drop
- else keep testing
Exposure: Thompson sampling on the interest rate (more slots for designs that look better, but every live test
still gets some, so a slow starter isn't killed by luck).
"""
from __future__ import annotations

import datetime as dt
import json
import random
import threading
import uuid
from collections import defaultdict

from . import config as C

MIN_VIEWS = 300
WIN_ABS = 0.01
WIN_X = 1.5
DROP_X = 0.5
SAVE_W = 0.3
CHANNELS = {"basalam": "غرفه‌ی باسلام", "instagram": "پیج اینستاگرام", "telegram": "کانال تلگرام", "other": "سایر"}
STAGES = {"pretest": "پیش‌آزمون با عکس", "smallbuy": "خرید کم", "reorder": "سفارش دوباره"}
SOURCES = {"report": "گزارش (باسلام)", "etsy": "Etsy", "google": "گوگل", "suggest": "پیشنهاد جست‌وجو",
           "voice": "نظر خریداران", "needs": "نیاز کادو", "instagram": "اینستاگرام", "telegram": "تلگرام",
           "trendyol": "ترندیول (ترکیه)", "ads": "گوگل ادز", "maker": "پیشنهاد سازنده",
           "manual": "ایده‌ی خودم"}
FIELDS = ("views", "saves", "messages", "carts", "orders", "noes")   # noes: «نه»/skip taps — the negative signal
EXPLORE = 0.2          # share of showcase slots always kept for brand-new ideas (under MIN_VIEWS), so new trends get seen
_lock = threading.Lock()


def _f():
    d = C.DATA_DIR / "lab"
    d.mkdir(parents=True, exist_ok=True)
    return d / "tests.json"


def load() -> list[dict]:
    f = _f()
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else []


def save(tests: list[dict]) -> None:
    f = _f()
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps(tests, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(f)


def add(name: str, channel: str, source: str, price: int | None = None, query: str = "", stage: str = "pretest",
        control: bool = False, note: str = "", tags: str = "") -> dict:
    t = {"id": uuid.uuid4().hex[:8], "name": name.strip()[:120], "query": query.strip()[:120],
         "channel": channel if channel in CHANNELS else "other", "source": source if source in SOURCES else "manual",
         "stage": stage if stage in STAGES else "pretest", "price": price, "control": bool(control),
         "note": note.strip()[:300],
         "tags": [x.strip() for x in tags.replace("،", ",").split(",") if x.strip()][:8], "started": dt.date.today().isoformat(), "closed": "", "metrics": []}
    with _lock:
        tests = load()
        tests.append(t)
        save(tests)
    return t


def update(tid: str, numbers: dict, close: str = "") -> dict | None:
    """numbers: cumulative totals so far, e.g. {'views': 820, 'messages': 9}."""
    with _lock:
        tests = load()
        for t in tests:
            if t["id"] == tid:
                row = {"date": dt.date.today().isoformat(), **{k: max(0, int(numbers.get(k) or 0)) for k in FIELDS}}
                t["metrics"] = [m for m in t["metrics"] if m["date"] != row["date"]] + [row]
                if close in ("win", "drop", "stop"):
                    t["closed"] = close
                save(tests)
                return t
    return None


def last(t: dict) -> dict:
    return t["metrics"][-1] if t["metrics"] else {k: 0 for k in FIELDS}


def interest(m: dict) -> float:
    return m.get("messages", 0) + m.get("carts", 0) + m.get("orders", 0) + SAVE_W * m.get("saves", 0)


def no_rate(t: dict) -> float | None:
    m = last(t)
    return m.get("noes", 0) / m["views"] if m.get("views") else None


def rate(t: dict) -> float | None:
    m = last(t)
    return interest(m) / m["views"] if m.get("views") else None


def control_rate(tests: list[dict], channel: str) -> float | None:
    cs = [t for t in tests if t["control"] and t["channel"] == channel and last(t).get("views")]
    if not cs:
        return None
    v = sum(last(t)["views"] for t in cs)
    return sum(interest(last(t)) for t in cs) / v if v else None


def verdict(t: dict, ctrl: float | None) -> tuple[str, str]:
    """(code, Persian sentence)."""
    if t["closed"]:
        return t["closed"], {"win": "برنده (بسته شد)", "drop": "کنار گذاشته شد", "stop": "متوقف شد"}[t["closed"]]
    if t["control"]:
        return "control", "طرح کنترل (مبنای مقایسه)"
    m = last(t)
    r = rate(t)
    if not m.get("views") or m["views"] < MIN_VIEWS:
        return "early", f"زود است؛ حداقل {MIN_VIEWS} بازدید لازم است"
    bar = max(WIN_ABS, WIN_X * ctrl) if ctrl else WIN_ABS
    if r >= bar:
        return "win", "برنده: سفارش کم از سازنده" if t["stage"] == "pretest" else "برنده: سفارش دوباره، بیشتر"
    if m["views"] >= 2 * MIN_VIEWS and r < DROP_X * (ctrl if ctrl else WIN_ABS):
        return "drop", "ضعیف: کنار بگذارید"
    return "keep", "ادامه‌ی آزمایش"


def exposure(tests: list[dict], draws: int = 2000, seed: int | None = None) -> dict[str, float]:
    """Share of the next posts / showcase slots per live test, per channel (Thompson sampling)."""
    rnd = random.Random(seed)
    live = [t for t in tests if not t["closed"] and not t["control"]]
    by_ch = defaultdict(list)
    for t in live:
        by_ch[t["channel"]].append(t)
    out = {}
    for ts in by_ch.values():
        new = [t for t in ts if last(t).get("views", 0) < MIN_VIEWS]
        old = [t for t in ts if t not in new]
        if new and old:      # keep EXPLORE for the new ones, split the rest by Thompson sampling
            for t in new:
                out[t["id"]] = EXPLORE / len(new)
            scale, ts = 1 - EXPLORE, old
        else:
            scale = 1.0
        wins = defaultdict(int)
        for _ in range(draws):
            best = max(ts, key=lambda t: rnd.betavariate(1 + interest(last(t)),
                                                          1 + max(0.0, last(t).get("views", 0) - interest(last(t)))))
            wins[best["id"]] += 1
        for t in ts:
            out[t["id"]] = scale * wins[t["id"]] / draws
    return out


def board() -> dict:
    tests = load()
    ctrl = {ch: control_rate(tests, ch) for ch in CHANNELS}
    exp = exposure(tests, seed=1)
    rows = []
    for t in tests:
        code, text = verdict(t, ctrl.get(t["channel"]))
        rows.append({**t, "now": last(t), "rate": rate(t), "no_rate": no_rate(t), "verdict": code, "verdict_fa": text,
                     "share": exp.get(t["id"])})
    by_src = defaultdict(lambda: {"tests": 0, "wins": 0})
    for r in rows:
        if r["control"]:
            continue
        s = by_src[r["source"]]
        s["tests"] += 1
        s["wins"] += r["verdict"] == "win"
    by_tag = defaultdict(lambda: {"tests": 0, "wins": 0, "drops": 0})
    for r in rows:
        if r["control"] or r["verdict"] in ("early", "keep"):
            continue                       # only decided tests teach us something
        for tg in r.get("tags") or []:
            s = by_tag[tg]
            s["tests"] += 1
            s["wins"] += r["verdict"] == "win"
            s["drops"] += r["verdict"] == "drop"
    return {"rows": rows, "control": ctrl, "sources": dict(by_src), "tags": dict(by_tag)}
