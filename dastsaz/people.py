"""People radar: an always-on, low-cost search for promising Instagram pages (works like a tiny search engine).

* frontier: every handle we have heard of, with a "promise" score. Filled for free from what we already read:
  @mentions in the captions of pages we profiled, Instagram links in Twitter bios, Pinterest pins that link to
  Instagram, @handles in public Telegram channels. A mention by a good page passes part of that page's score on
  (like PageRank): good pages tend to know good pages.
* every night, a fixed budget (default 15 cents of Apify): the most promising handles are profiled (80%) plus a
  random few for discovery (20%); each gets the usual grade (engagement, real comments, recent posts, Persian,
  fit, taste from photos). Good pages pass promise to the handles they mention.
* every 30 days the good pages are checked again: follower growth marks pages that are rising.
* weights are learned: thumbs up/down by us and the supplier (later: sales per discount code) nudge how much each
  signal counts. Nothing is ever contacted automatically.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import random
import re

from . import config as C
from . import influencers as I

log = logging.getLogger(__name__)
HANDLE = re.compile(r"(?<![\w.])@([A-Za-z0-9_][A-Za-z0-9_.]{2,29})")
SOURCE_PRIOR = {"mention": 0.35, "twitter": 0.3, "pinterest": 0.3, "telegram": 0.2, "manual": 0.9, "tagged": 0.4}
FEATURES = ("eng_band", "comments", "active", "persian", "fit", "taste", "growth")
W0 = {"eng_band": 1.0, "comments": 0.4, "active": 0.6, "persian": 0.4, "fit": 0.8, "taste": 0.8, "growth": 0.5}
SKIP = {"instagram", "explore", "p", "reel", "reels", "stories", "gmail", "yahoo", "hotmail", "com"}


def _f(name: str):
    return I._dir() / name


def _load(name: str, default):
    f = _f(name)
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else default


def _save(name: str, obj) -> None:
    _f(name).write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")


def frontier() -> dict:
    return _load("frontier.json", {})


def weights() -> dict:
    return _load("weights.json", dict(W0))


def clean(h: str) -> str:
    h = str(h or "").strip().lstrip("@").rstrip(".").lower()
    return "" if (not h or h in SKIP or len(h) < 3) else h


def add(handles, prior: float, source: str, parent: str = "", fr: dict | None = None, known: set | None = None) -> int:
    """Add or strengthen candidates. The same handle heard again from more places gets more promise."""
    fr = fr if fr is not None else frontier()
    known = known or set()
    n = 0
    for h in handles:
        h = clean(h)
        if not h or h in known:
            continue
        c = fr.get(h)
        if c is None:
            fr[h] = {"p": round(prior, 3), "src": [source], "parent": parent, "seen": C.today().isoformat()}
            n += 1
        else:
            c["p"] = round(min(1.0, c["p"] + prior * 0.5), 3)      # heard again: more promise
            if source not in c["src"]:
                c["src"].append(source)
    return n


def harvest(fr: dict, known: set) -> dict:
    """Free candidates from data we already have."""
    got = {}
    d = I.latest() or {"rows": []}
    for x in d["rows"]:                                      # mentions kept from profiled pages
        g = {"A": 1.0, "B": 0.7}.get(x.get("grade"), 0.3)
        got["mention"] = got.get("mention", 0) + add(x.get("mentions") or [], SOURCE_PRIOR["mention"] * g,
                                                     "mention", x["u"], fr, known)
        if x.get("src") == "twitter" and x.get("ig"):
            got["twitter"] = got.get("twitter", 0) + add([x["ig"]], SOURCE_PRIOR["twitter"], "twitter", x["u"], fr, known)
    try:
        from . import pinterest
        pins = (pinterest.latest() or {}).get("pins", [])
        hs = [m.group(1) for p in pins for m in [re.search(r"instagram\.com/([A-Za-z0-9_.]{3,30})", p.get("link") or "")] if m]
        got["pinterest"] = add(hs, SOURCE_PRIOR["pinterest"], "pinterest", "", fr, known)
    except Exception as e:  # noqa: BLE001
        log.info("people harvest pinterest: %s", e)
    try:
        from . import telegram
        hs = [h for ps in telegram.posts().values() for p in ps[-200:] for h in HANDLE.findall(p.get("text") or "")]
        got["telegram"] = add(hs, SOURCE_PRIOR["telegram"], "telegram", "", fr, known)
    except Exception as e:  # noqa: BLE001
        log.info("people harvest telegram: %s", e)
    return got


def features(x: dict, today: str) -> dict:
    e = x.get("eng", 0)
    likes = max(1, x.get("med", 0) - x.get("cmed", 0))
    cr = x.get("cmed", 0) / likes
    try:
        days = (dt.date.fromisoformat(today) - dt.date.fromisoformat(x.get("last") or "")).days
    except ValueError:
        days = 60
    return {"eng_band": 1.0 if 2 <= e <= 8 else 0.6 if (1 <= e < 2 or 8 < e <= 15) else 0.0,
            "comments": 1.0 if 0.01 <= cr <= 0.25 else 0.3,
            "active": 1.0 if days <= 30 else 0.5 if days <= 90 else 0.0,
            "persian": 1.0 if x.get("fa", 1) >= 0.5 else 0.0,
            "fit": x.get("fit", 0) / 10, "taste": x.get("taste", 5) / 10,
            "growth": max(0.0, min(1.0, x.get("growth", 0) / 10))}      # % per month, 10% = full


def value(x: dict, w: dict | None = None, today: str | None = None) -> float:
    """0-100 from the learned weights."""
    w = w or weights()
    f = features(x, today or C.today().isoformat())
    tot = sum(max(0.0, w.get(k, 0)) for k in FEATURES) or 1
    return round(100 * sum(max(0.0, w.get(k, 0)) * f[k] for k in FEATURES) / tot, 1)


def learn(rows: list[dict], lr: float = 0.15) -> dict:
    """Thumbs up/down nudge the weights (a simple perceptron): a feature that is high on liked pages and low on
    disliked ones counts more. Weights stay between 0.05 and 3."""
    w = dict(weights())
    today = C.today().isoformat()
    voted = [x for x in rows if x.get("vote") in (1, -1)]
    if len(voted) < 6:
        return w
    for x in voted:
        f = features(x, today)
        pred = value(x, w, today) / 100 - 0.5
        err = x["vote"] * 0.5 - pred
        for k in FEATURES:
            w[k] = round(min(3.0, max(0.05, w[k] + lr * err * (f[k] - 0.5))), 3)
    _save("weights.json", w)
    return w


def vote(u: str, v: int) -> bool:
    d = I.latest()
    if not d:
        return False
    hit = False
    for x in d["rows"]:
        if x["u"] == u:
            x["vote"] = v if v in (1, -1) else 0
            hit = True
            if v == 1:                                          # a liked page becomes a strong seed
                fr = frontier()
                add(x.get("mentions") or [], 0.6, "mention", u, fr, {r["u"] for r in d["rows"]})
                _save("frontier.json", fr)
    if hit:
        (I._dir() / "latest.json").write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    return hit


def pick(fr: dict, n: int, rnd: random.Random) -> list[str]:
    todo = [h for h, c in fr.items() if not c.get("done")]
    best = sorted(todo, key=lambda h: -fr[h]["p"])
    k = max(1, int(n * 0.8))
    chosen = best[:k]
    rest = best[k:]
    chosen += rnd.sample(rest, min(n - len(chosen), len(rest)))
    return chosen


def nightly(budget: float = 0.15, ap=None, rnd: random.Random | None = None) -> dict:
    """One night: harvest free candidates, profile the most promising within the budget, grade, pass promise on,
    re-check a few good pages for growth, learn from votes."""
    from .etsy import Apify
    ap = ap or Apify(C.secret("APIFY_TOKEN") or "none")
    rnd = rnd or random.Random(C.today().isoformat())
    d = I.latest() or {"rows": []}
    rows = {x["u"]: x for x in d["rows"]}
    fr = frontier()
    known = set(rows) | set(d.get("checked", []))
    got = harvest(fr, known)
    from . import igapi
    free = igapi.ready()                                       # Instagram's own API: free, ~120 pages a night
    per = 0.0065                                               # ~ dollars per profile on Apify
    n_new = 120 if free else max(1, int(budget * 0.85 / per))
    n_old = 20 if free else max(0, int(budget * 0.15 / per))
    today = C.today().isoformat()
    new = pick(fr, n_new, rnd)
    old = [u for u, x in rows.items() if x.get("grade") in ("A", "B") and x.get("src") != "twitter"
           and (x.get("checked_on") or "2000-01-01") <= (C.today() - dt.timedelta(days=30)).isoformat()][:n_old]
    users = new + old
    if not users:
        _save("frontier.json", fr)
        return {"harvest": got, "profiled": 0}
    skipped: list[str] = []
    if not free and budget <= 0:                               # no free API yet and no Apify budget: only collect
        _save("frontier.json", fr)
        return {"date": today, "harvest": got, "profiled": 0, "waiting": "instagram token"}
    if free:
        profs, skipped = igapi.profiles(users)
        usd = 0.0
    else:
        r = ap.run({"usernames": users}, budget, actor=I.PROFILE_ACTOR)
        profs = ap.items(r["defaultDatasetId"]) if r.get("defaultDatasetId") else []
        usd = ap.cost(r)
    for u in skipped:                                          # personal or private: not visible to the free API
        if u in fr:
            fr[u]["done"], fr[u]["personal"] = today, True
    fresh, added, rising = [], 0, 0
    for p in profs:
        u = str(p.get("username") or "").lower()
        st = I.stats(p)
        st["mentions"] = sorted({clean(m) for q in (p.get("latestPosts") or []) for m in
                                 (q.get("mentions") or []) + HANDLE.findall(str(q.get("caption") or ""))} - {u, ""})[:40]
        if u in rows:                                          # a re-check: growth per month
            x = rows[u]
            prev_f, prev_d = x.get("followers", 0), x.get("checked_on") or x.get("first") or today
            days = max(1, (dt.date.fromisoformat(today) - dt.date.fromisoformat(prev_d)).days)
            if prev_f:
                x["growth"] = round((st["followers"] - prev_f) / prev_f * 100 * 30 / days, 1)
                rising += x["growth"] >= 5
            x.update({k: st[k] for k in ("followers", "eng", "med", "cmed", "last", "fa", "mentions")})
            x["checked_on"] = today
            continue
        if u in fr:
            fr[u]["done"] = today
        if not (I.MIN_F * 0.6 <= st["followers"] <= I.MAX_F * 1.2):
            continue
        st.update({"src": "instagram", "niche": "رادار (" + "، ".join(fr.get(u, {}).get("src", ["?"])) + ")",
                   "first": today, "checked_on": today, "pick": False, "parent": fr.get(u, {}).get("parent", "")})
        fresh.append(st)
    for u in new:
        if u in fr:
            fr[u]["done"] = fr[u].get("done") or today
    if fresh:
        tags, c = I.ai.ask_json(I.ASK, [{"u": x["u"], "bio": x["bio"], "captions": x["captions"]} for x in fresh],
                                C.secret("OPENROUTER_API_KEY"), max_tokens=6000)
        usd += c
        by = {str(t.get("u")).lower(): t for t in tags.get("items") or []}
        for x in fresh:
            t = by.get(x["u"].lower(), {})
            x["kind"] = t.get("kind") if t.get("kind") in I.KINDS else "other"
            x["fit"] = I._n(t.get("fit"))
            x["note"] = str(t.get("note") or "")[:160]
            x.pop("captions", None)
        usd += I.score_rows(fresh)
        for x in fresh:
            g = {"A": 1.0, "B": 0.6}.get(x.get("grade"), 0.15)
            if x["kind"] in ("creator", "maker"):
                add(x.get("mentions") or [], SOURCE_PRIOR["mention"] * g * 1.5, "mention", x["u"], fr, known | {x["u"]})
            d["rows"].append(x)
            added += 1
    w = learn(d["rows"])
    for x in d["rows"]:
        x["value"] = value(x, w, today)
    d["rows"].sort(key=lambda x: (I.ORDER.get(x["kind"], 3), -x.get("value", 0)))
    d["usd"] = round(d.get("usd", 0) + usd, 3)
    d["checked"] = sorted(set(d.get("checked", [])) | {u.lower() for u in new})
    d.setdefault("radar", []).append({"date": today, "harvest": got, "profiled": len(profs), "added": added,
                                      "good": sum(1 for x in fresh if x.get("grade") in ("A", "B") and x["kind"] in ("creator", "maker")),
                                      "rising": rising, "usd": round(usd, 3), "via": "instagram" if free else "apify", "personal": len(skipped), "frontier": sum(1 for c in fr.values() if not c.get("done"))})
    d["radar"] = d["radar"][-60:]
    (I._dir() / "latest.json").write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    _save("frontier.json", fr)
    return d["radar"][-1]


def add_manual(handles: list[str]) -> int:
    """Handles typed in by us or the supplier: highest promise, profiled first next night."""
    fr = frontier()
    d = I.latest() or {"rows": []}
    n = add([h.strip().rstrip("/").rsplit("/", 1)[-1] for h in handles], SOURCE_PRIOR["manual"], "manual", "",
            fr, {x["u"] for x in d["rows"]})
    _save("frontier.json", fr)
    return n


def bootstrap(ap=None, budget: float = 0.4) -> dict:
    """First fill of the queue: profile the good pages we already have once, to read whom they mention."""
    from .etsy import Apify
    ap = ap or Apify(C.secret("APIFY_TOKEN"))
    d = I.latest() or {"rows": []}
    good = [x for x in d["rows"] if x.get("grade") in ("A", "B") and x.get("src") != "twitter"
            and x["kind"] in ("creator", "maker") and not x.get("mentions")]
    users = [x["u"] for x in good][: int(budget / 0.0065)]
    if not users:
        return {"profiled": 0}
    r = ap.run({"usernames": users}, budget, actor=I.PROFILE_ACTOR)
    profs = {str(p.get("username") or "").lower(): p for p in (ap.items(r["defaultDatasetId"]) if r.get("defaultDatasetId") else [])}
    fr = frontier()
    known = {x["u"].lower() for x in d["rows"]} | set(d.get("checked", []))
    today = C.today().isoformat()
    n = 0
    for x in good:
        p = profs.get(x["u"].lower())
        if not p:
            continue
        x["mentions"] = sorted({clean(m) for q in (p.get("latestPosts") or []) for m in
                                (q.get("mentions") or []) + HANDLE.findall(str(q.get("caption") or ""))} - {x["u"].lower(), ""})[:40]
        x["checked_on"] = x.get("checked_on") or today
        g = {"A": 1.0, "B": 0.6}.get(x.get("grade"), 0.2)
        n += add(x["mentions"], SOURCE_PRIOR["mention"] * g * 1.5, "mention", x["u"], fr, known)
    d["usd"] = round(d.get("usd", 0) + ap.cost(r), 3)
    (I._dir() / "latest.json").write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    harvest(fr, known)
    _save("frontier.json", fr)
    return {"profiled": len(profs), "new_candidates": n, "frontier": sum(1 for c in fr.values() if not c.get("done")),
            "usd": round(ap.cost(r), 3)}
