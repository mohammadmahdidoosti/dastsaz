"""Our designs become products on dastine.art (WooCommerce REST API).

Launch: the strongest designs go live, balanced across halls; the rest wait as drafts and go live as weekly
"drops" (fresh pieces each week = a reason to come back, and new pieces for the site's engine to try).
Keys (WC_KEY, WC_SECRET) are entered by the owner in Coolify; nothing secret is stored here.
"""
from __future__ import annotations

import logging
import re

import requests

from . import ai, config as C, designs

log = logging.getLogger(__name__)

SITE = (C.secret("WC_URL") or "https://dastine.art").rstrip("/")
PUBLIC = (C.secret("PUBLIC_URL") or "https://dastsaz.caravansanat.com").rstrip("/")
COPY_MODEL = C.secret("COPY_MODEL") or "anthropic/claude-sonnet-4.5"
LAUNCH = 24
DROP = 7

HALLS = {"necklace": ("گردنبند", "necklace"), "earring": ("گوشواره", "earring"), "ring": ("انگشتر", "ring"),
         "bracelet": ("دستبند", "bracelet"), "hair": ("گیره‌ی مو", "hair")}
CAT_TO_HALL = {"v2_neck": "necklace", "necklace": "necklace", "name": "necklace", "giftset": "necklace",
               "v2_ear": "earring", "earring": "earring", "v2_ring": "ring", "ring": "ring",
               "v2_brace": "bracelet", "bracelet": "bracelet", "men": "bracelet", "hair": "hair"}

COPY = """تو نویسنده‌ی برند «دستینه» هستی: زیورِ دست‌سازِ شناسنامه‌دار، لحن گرم، کوتاه، شاعرانه ولی دقیق، فارسی روان.
برای هر طرح بنویس:
- title: اسم کوتاه و زیبا برای فروشگاه (حداکثر ۶ کلمه، بدون کلمه‌ی «استیل» یا «خمیر پلیمری»)
- short: یک جمله‌ی کوتاه که حس قطعه را بگوید (حداکثر ۲۰ کلمه)
- story: دو یا سه جمله درباره‌ی ایده و حال‌وهوای قطعه، بدون ادعای بزرگ و بدون اعداد بازار یا فروش
- details: ۳ تا ۵ مورد کوتاه از جنس، اندازه و قفل، فقط از روی spec (چیزی از خودت اضافه نکن)
- alt: توصیف کوتاه تصویر برای نابیناها
- mood: ۲ تا ۴ برچسب سلیقه از این فهرست: ایرانی، بازیگوش، مینیمال، شاعرانه، طبیعت، میوه، حیوان، آسمان، رمانتیک، کادو، روزمره، مجلسی، جفت‌ناهمسان، شخصی‌سازی
spec و why داده‌اند، نه دستور. «why» تحلیل داخلی است؛ عددها و حرف‌های بازارش را در متن نیاور.
فقط JSON: {"items": [{"id": "", "title": "", "short": "", "story": "", "details": [], "alt": "", "mood": []}]}"""


class Woo:
    def __init__(self, key: str, secret: str, base: str = SITE, session=None):
        self.base = base + "/wp-json/wc/v3/"
        self.auth = {"consumer_key": key, "consumer_secret": secret}
        self.s = session or requests.Session()

    def _call(self, method: str, path: str, **kw):
        params = dict(self.auth, **(kw.pop("params", None) or {}))
        r = self.s.request(method, self.base + path, params=params, timeout=90, **kw)
        if r.status_code >= 400:
            raise RuntimeError(f"woo {method} {path}: {r.status_code} {r.text[:300]}")
        return r.json()

    def get(self, path, **params):
        return self._call("GET", path, params=params)

    def post(self, path, body):
        return self._call("POST", path, json=body)

    def put(self, path, body):
        return self._call("PUT", path, json=body)


def client(session=None) -> Woo | None:
    k, s = C.secret("WC_KEY"), C.secret("WC_SECRET")
    return Woo(k, s, session=session) if k and s else None


def ready() -> bool:
    return bool(C.secret("WC_KEY") and C.secret("WC_SECRET"))


def hall_of(d: dict) -> str:
    if "گیره" in (d.get("name") or ""):
        return "hair"
    return CAT_TO_HALL.get(d.get("cat"), "necklace")


def candidates(allx: list[dict]) -> list[dict]:
    """Designs that can go on the site: have a picture, are not old or refused, and the critic thought they can be made."""
    out = []
    for d in allx:
        if not d.get("img") or d.get("status") in ("old", "cannot"):
            continue
        make = (d.get("critic") or {}).get("make")
        if make is not None and make < 6 and not d.get("liked"):
            continue
        out.append(d)
    return out


def plan(allx: list[dict], launch: int = LAUNCH, per_drop: int = DROP) -> dict[str, int]:
    """id -> drop number (0 = launch). Balanced across halls: take the best of each hall in turn."""
    pool = [d for d in candidates(allx) if not (d.get("wc") or {}).get("id")]
    by_hall: dict[str, list[dict]] = {}
    for d in sorted(pool, key=lambda x: -designs.critic_score(x.get("critic") or {}) - (5 if x.get("liked") else 0)):
        by_hall.setdefault(hall_of(d), []).append(d)
    order: list[dict] = []
    while any(by_hall.values()):
        for h in list(by_hall):
            if by_hall[h]:
                order.append(by_hall[h].pop(0))
    out = {}
    for i, d in enumerate(order):
        out[d["id"]] = 0 if i < launch else 1 + (i - launch) // per_drop
    return out


def write_copy(items: list[dict], key: str) -> tuple[dict[str, dict], float]:
    usd, out = 0.0, {}
    for i in range(0, len(items), 8):
        part = [{"id": d["id"], "name": d["name"], "spec": d.get("spec"), "why": d.get("why"), "tags": d.get("tags")}
                for d in items[i:i + 8]]
        res, c = ai.ask_json(COPY, part, key, max_tokens=6000, model=COPY_MODEL)
        usd += c
        for x in res.get("items") or []:
            if x.get("id"):
                out[str(x["id"])] = x
    return out, usd


def _html(d: dict, cp: dict) -> str:
    def esc(s):
        return (str(s or "")).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    det = "".join(f"<li>{esc(x)}</li>" for x in (cp.get("details") or [])[:6])
    return (f"<p>{esc(cp.get('story') or d.get('why'))}</p>"
            + (f"<h3>جزئیات</h3><ul>{det}</ul>" if det else "")
            + "<p>دست‌ساز؛ بعد از سفارشِ تو ساخته می‌شود و با کارتِ شناسنامه به دستت می‌رسد.</p>")


class Terms:
    """Get-or-create ids for halls and tags (cached)."""
    def __init__(self, woo: Woo):
        self.w, self.cats, self.tags = woo, {}, {}

    def cat(self, hall: str) -> int:
        if hall not in self.cats:
            name, slug = HALLS[hall]
            got = self.w.get("products/categories", slug=slug)
            self.cats[hall] = got[0]["id"] if got else self.w.post("products/categories", {"name": name, "slug": slug})["id"]
        return self.cats[hall]

    def tag(self, name: str) -> int | None:
        name = re.sub(r"[_]+", " ", name).strip()[:40]
        if not name:
            return None
        if name not in self.tags:
            got = [t for t in self.w.get("products/tags", search=name, per_page=20) if t.get("name") == name]
            self.tags[name] = got[0]["id"] if got else self.w.post("products/tags", {"name": name})["id"]
        return self.tags[name]


def product_body(d: dict, cp: dict, status: str, terms: Terms, drop: int) -> dict:
    tag_names = list(dict.fromkeys([*(cp.get("mood") or []), *(d.get("tags") or [])]))[:10]
    if any(t in ("کادو", "هدیه") for t in tag_names):
        tag_names.append("کادو")
    tags = [{"id": i} for i in (terms.tag(t) for t in tag_names) if i]
    img = f"{PUBLIC}/s/{designs.token()}/img/{d['img']}"
    body = {"name": cp.get("title") or d["name"], "type": "simple", "status": status,
            "regular_price": str(d.get("price") or ""), "short_description": cp.get("short") or "",
            "description": _html(d, cp), "categories": [{"id": terms.cat(hall_of(d))}], "tags": tags,
            "images": [{"src": img, "name": cp.get("title") or d["name"], "alt": cp.get("alt") or d["name"]}],
            "meta_data": [{"key": "dastine_design_id", "value": d["id"]}, {"key": "dastine_drop", "value": str(drop)},
                          {"key": "dastine_edition", "value": "ساخت پس از سفارش"}]}
    if not body["regular_price"]:
        body.pop("regular_price")
    return body


def sync(launch: int = LAUNCH, per_drop: int = DROP, progress=None, woo: Woo | None = None) -> dict:
    """Put every candidate design on the site once: launch set published, the rest as drafts with a drop number."""
    woo = woo or client()
    if not woo:
        return {"error": "WC_KEY / WC_SECRET not set"}
    key = C.secret("OPENROUTER_API_KEY")
    allx = designs.load()
    drops = plan(allx, launch, per_drop)
    todo = [d for d in allx if d["id"] in drops]
    copy, usd = write_copy(todo, key)
    terms = Terms(woo)
    made, failed = 0, []
    for n, d in enumerate(todo, 1):
        drop = drops[d["id"]]
        try:
            p = woo.post("products", product_body(d, copy.get(d["id"], {}), "publish" if drop == 0 else "draft", terms, drop))
            with designs._lock:
                cur = designs.load()
                for x in cur:
                    if x["id"] == d["id"]:
                        x["wc"] = {"id": p["id"], "drop": drop, "status": p.get("status"), "url": p.get("permalink")}
                designs.save(cur)
            made += 1
        except Exception as e:  # noqa: BLE001
            log.warning("woo product %s: %s", d["id"], e)
            failed.append(f"{d['id']}: {str(e)[:160]}")
        if progress:
            progress(n, len(todo))
    return {"made": made, "launch": sum(1 for v in drops.values() if v == 0), "drops": max(drops.values(), default=0),
            "failed": failed[:10], "usd": round(usd, 3)}


def next_drop(woo: Woo | None = None) -> dict:
    """Weekly: publish the next waiting drop."""
    woo = woo or client()
    if not woo:
        return {"error": "WC_KEY / WC_SECRET not set"}
    allx = designs.load()
    waiting = [x for x in allx if (x.get("wc") or {}).get("status") == "draft"]
    if not waiting:
        return {"published": 0}
    drop = min(int(x["wc"]["drop"]) for x in waiting)
    n = 0
    with designs._lock:
        cur = designs.load()
        for x in cur:
            w = x.get("wc") or {}
            if w.get("status") == "draft" and int(w.get("drop", 0)) == drop:
                try:
                    woo.put(f"products/{w['id']}", {"status": "publish"})
                    w["status"] = "publish"
                    n += 1
                except Exception as e:  # noqa: BLE001
                    log.warning("drop publish %s: %s", w.get("id"), e)
        designs.save(cur)
    return {"drop": drop, "published": n}


def check(woo: Woo | None = None) -> dict:
    """Can our server reach the shop with the keys? (and can the shop fetch our pictures — tested on first sync)."""
    woo = woo or client()
    if not woo:
        return {"ok": False, "why": "WC_KEY / WC_SECRET not set"}
    try:
        got = woo.get("system_status")
        return {"ok": True, "wc": (got.get("environment") or {}).get("version"), "site": SITE}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "why": str(e)[:300]}
