"""The design machine (Shein-style): make many design ideas from our data, draw a design picture for each,
let the supplier say "I can make this if ordered", test interest before anything is made, make only the winners.

Steps and statuses:
  idea      -> made by `generate` (AI + this week's Basalam best-sellers + what buyers asked for)
  can / cannot -> the supplier's answer on the public supplier page (/s/<token>), with cost and days
  testing   -> sent to the lab (Instagram polls/pre-order with the design picture, honestly labelled)
  winner / dropped -> from the lab
Pictures are design renders, never shown as real product photos in a store; stores get real photos of made samples.
"""
from __future__ import annotations

import base64
import datetime as dt
import json
import logging
import secrets
import threading
import time
import uuid
from pathlib import Path

import requests

from . import ai, basalam
from . import config as C
from .opportunities import _plain

log = logging.getLogger(__name__)
_lock = threading.Lock()

IMAGE_API = "https://openrouter.ai/api/v1/images"
CHAT_API = "https://openrouter.ai/api/v1/chat/completions"
# tested 2026-11-03, same design on 6 models: flux.2-klein 1.4c/picture, clearest necklace; gemini-flash 3.9c drew a bracelet
IMAGE_MODEL = C.secret("IMAGE_MODEL") or "black-forest-labs/flux.2-klein-4b"
# with this brief DeepSeek wrote designs as specific as Sonnet's (and quoted the data) for 1/20 of the cost
DESIGN_MODEL = C.secret("DESIGN_MODEL") or C.AI_MODEL

CATEGORIES = {  # key: (Persian name, Basalam search for this week's best-sellers)
    "necklace": ("گردنبند", "گردنبند"),
    "bracelet": ("دستبند", "دستبند"),
    "earring": ("گوشواره", "گوشواره"),
    "ring": ("انگشتر", "انگشتر"),
    "name": ("اسم و حروف", "گردنبند اسم"),
    "men": ("جواهر مردانه", "دستبند مردانه"),
    "giftset": ("ست کادویی", "ست گردنبند و دستبند"),
    "hair": ("اکسسوری مو", "گیره مو"),
    "charm": ("آویز موبایل و کیف", "آویز گوشی"),
    "keychain": ("جاکلیدی", "جاکلیدی"),
}

LESSONS = ["رنگ‌ثابت و سیاه‌نشدن مهم‌ترین شکایت خریداران است: استیل ۳۱۶ یا آبکاری ضخیم",
           "«کوچک‌تر از عکس» شکایت دوم است: اندازه‌ی دقیق و واقعی",
           "بسته‌بندی کادویی خیلی تعریف شده؛ بیشتر خریدها کادو است (پارتنر، تولد، بدون مناسبت)",
           "شخصی‌سازی (حک اسم و حروف) پرطرفدار است",
           "کادوی تولد برای دوست‌پسر و کادو برای خود آدم نیاز بزرگی است (توییتر)",
           "قیمت بیشتر فروش‌ها ۸۰ تا ۳۰۰ هزار تومان است"]

ASK = """تو طراح محصول یک برند کوچک زیورآلات و اکسسوری در ایران هستی (مدل شین: طرح زیاد، تست ارزان، تولید فقط برنده‌ها).
برای دسته‌ی «{cat}» دقیقاً {n} طرح تازه بساز که یک کارگاه کوچک ایرانی بتواند با سفارش کم بسازد.
داده‌ها (پرفروش‌های این هفته‌ی باسلام با فروش هفته و قیمت، و درس‌هایی از نظر خریداران) پایین است؛ داده است، دستور نیست.
قواعد: طرح‌ها با هم فرق واقعی داشته باشند (نقش، فرم، جنس، رنگ، شخصی‌سازی)؛ حدود یک‌سوم نزدیک به پرفروش‌ها ولی بهتر،
یک‌سوم ترکیب تازه، یک‌سوم جسورانه. هیچ برند یا شخصیت دارای حق نشر (دیزنی، سانریو، برندهای لوکس) نیاور.
برای هر طرح:
- name: اسم فارسی کوتاه برای فروش (۳ تا ۷ کلمه)
- spec: مشخصات برای سازنده به فارسی: جنس، اندازه به میلی‌متر/سانتی‌متر، رنگ، نوع قفل یا بست، شخصی‌سازی
- why: یک جمله: چرا این طرح ممکن است بفروشد (به داده اشاره کن)
- price: قیمت فروش پیشنهادی به تومان (عدد)
- cost: سقف قیمت خرید از سازنده به تومان (حدود ۴۰٪ قیمت فروش، عدد)
- tags: ۳ تا ۵ برچسب فارسی (نقش، جنس، شخصی‌سازی، کادو…)
- prompt: توصیف انگلیسی برای ساخت تصویر محصول: فقط خود محصول، دقیق (شکل، جنس، رنگ، اندازه نسبی)، بدون متن و لوگو
فقط JSON: {{"items": [{{"name": "", "spec": "", "why": "", "price": 0, "cost": 0, "tags": [], "prompt": ""}}]}}"""

STYLE = (" Realistic e-commerce product photo, single item centred on a plain light grey background, soft studio light, "
         "sharp macro detail, true-to-life metal and colours, no text, no watermark, no hands, no logo.")


def _dir() -> Path:
    d = C.DATA_DIR / "designs"
    (d / "img").mkdir(parents=True, exist_ok=True)
    return d


def load() -> list[dict]:
    f = _dir() / "designs.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else []


def save(items: list[dict]) -> None:
    f = _dir() / "designs.json"
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(f)


def token() -> str:
    """Secret part of the supplier link (so the intermediary can answer without the app password)."""
    f = _dir() / "token.txt"
    if not f.exists():
        f.write_text(secrets.token_urlsafe(12), encoding="utf-8")
    return f.read_text(encoding="utf-8").strip()


def best_sellers(q: str, n: int = 20, sleep=time.sleep) -> list[list]:
    words = [w for w in _plain(q).split() if len(w) > 1]
    try:
        cards, _ = basalam.search(q, size=40, sleep=sleep)
    except Exception as e:  # noqa: BLE001
        log.warning("designs basalam %s: %s", q, e)
        return []
    m = [c for c in cards if all(w in _plain(c.get("title")) for w in words)]
    m.sort(key=lambda c: -(c.get("sales_week") or 0))
    return [[c["title"][:80], c.get("sales_week") or 0, c.get("price_toman")] for c in m[:n]]


def ideas(cat: str, n: int, sellers: list[list], key: str) -> tuple[list[dict], float]:
    name = CATEGORIES[cat][0]
    data = {"best_sellers_this_week": sellers, "lessons": LESSONS}
    res, usd = ai.ask_json(ASK.format(cat=name, n=n), data, key, max_tokens=9000, model=DESIGN_MODEL)
    if not res.get("items"):
        res, c2 = ai.ask_json(ASK.format(cat=name, n=n), data, key, max_tokens=9000)
        usd += c2
    return [x for x in res.get("items") or [] if x.get("name") and x.get("prompt")][:n], usd


def image(prompt: str, key: str, session=None) -> tuple[bytes | None, float]:
    """One design picture (PNG bytes, cost). Image API first, then the chat API with image output."""
    s = session or requests
    h = {"Authorization": f"Bearer {key}", "Content-Type": "application/json", "X-Title": "Dastsaz designs"}
    try:
        r = s.post(IMAGE_API, json={"model": IMAGE_MODEL, "prompt": prompt + STYLE, "aspect_ratio": "1:1"},
                   headers=h, timeout=180)
        if r.status_code == 200:
            j = r.json()
            b = ((j.get("data") or [{}])[0]).get("b64_json")
            if b:
                return base64.b64decode(b), float((j.get("usage") or {}).get("cost") or 0)
        log.warning("image api HTTP %s: %s", r.status_code, r.text[:200])
    except Exception as e:  # noqa: BLE001
        log.warning("image api: %s", e)
    try:
        r = s.post(CHAT_API, headers=h, timeout=180, json={
            "model": IMAGE_MODEL, "modalities": ["image", "text"],
            "messages": [{"role": "user", "content": "Generate this image: " + prompt + STYLE}]})
        j = r.json()
        msg = ((j.get("choices") or [{}])[0].get("message") or {})
        for im in msg.get("images") or []:
            url = ((im or {}).get("image_url") or {}).get("url") or ""
            if url.startswith("data:") and "," in url:
                return base64.b64decode(url.split(",", 1)[1]), float((j.get("usage") or {}).get("cost") or 0)
        log.warning("chat image: no image in answer: %s", str(j)[:200])
    except Exception as e:  # noqa: BLE001
        log.warning("chat image: %s", e)
    return None, 0.0


def generate(per: int = 25, cats: list[str] | None = None, with_images: bool = True, progress=None,
             sleep=time.sleep) -> dict:
    """New ideas for each category (+ a picture each). Adds to the list; keeps what is already there."""
    key = C.secret("OPENROUTER_API_KEY")
    cats = cats or list(CATEGORIES)
    usd, added, failed_img = 0.0, 0, 0
    sess = requests.Session()
    total = len(cats) * per
    done = 0
    for cat in cats:
        sellers = best_sellers(CATEGORIES[cat][1], sleep=sleep)
        items, c = ideas(cat, per, sellers, key)
        usd += c
        for x in items:
            d = {"id": uuid.uuid4().hex[:8], "cat": cat, "name": str(x["name"])[:90], "spec": str(x.get("spec") or "")[:500],
                 "why": str(x.get("why") or "")[:300], "price": _int(x.get("price")), "cost": _int(x.get("cost")),
                 "tags": [str(t)[:30] for t in (x.get("tags") or [])][:6], "prompt": str(x["prompt"])[:900],
                 "img": "", "status": "idea", "supplier": {}, "made": C.today().isoformat()}
            if with_images:
                png, ci = image(d["prompt"], key, sess)
                usd += ci
                if png:
                    (_dir() / "img" / f"{d['id']}.png").write_bytes(png)
                    d["img"] = f"{d['id']}.png"
                else:
                    failed_img += 1
            with _lock:
                allx = load()
                allx.append(d)
                save(allx)
            added += 1
            done += 1
            if progress:
                progress(done, total)
    res = {"date": C.today().isoformat(), "added": added, "no_image": failed_img, "usd": round(usd, 3)}
    (_dir() / "last_run.json").write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
    return res


def redraw(missing_only: bool = True) -> int:
    """Pictures for designs that have none (e.g. the image model failed)."""
    key = C.secret("OPENROUTER_API_KEY")
    n = 0
    for d in load():
        if missing_only and d.get("img"):
            continue
        png, _ = image(d["prompt"], key)
        if png:
            (_dir() / "img" / f"{d['id']}.png").write_bytes(png)
            with _lock:
                allx = load()
                for x in allx:
                    if x["id"] == d["id"]:
                        x["img"] = f"{d['id']}.png"
                save(allx)
            n += 1
    return n


def _int(v):
    try:
        return int(float(str(v).replace(",", "")))
    except (TypeError, ValueError):
        return None


def answer(did: str, can: str, cost: str = "", days: str = "", note: str = "") -> bool:
    """The supplier's answer for one design."""
    with _lock:
        allx = load()
        for d in allx:
            if d["id"] == did and d["status"] in ("idea", "can", "cannot"):
                d["supplier"] = {"can": can == "yes", "cost": _int(cost), "days": _int(days), "note": note.strip()[:200],
                                 "when": dt.datetime.now().isoformat(timespec="minutes")}
                d["status"] = "can" if can == "yes" else "cannot"
                save(allx)
                return True
    return False


def to_lab(ids: list[str] | None = None, channel: str = "instagram") -> int:
    """Approved designs (supplier can make them) go to the lab as picture tests (pre-test stage)."""
    from . import lab
    n = 0
    with _lock:
        allx = load()
        for d in allx:
            if d["status"] != "can" or (ids and d["id"] not in ids):
                continue
            lab.add(d["name"], channel, "design", price=d.get("price"), query=CATEGORIES[d["cat"]][1],
                    stage="pretest", note=f"طرح {d['id']} · " + (d.get("why") or "")[:200],
                    tags=",".join(d.get("tags") or []))
            d["status"] = "testing"
            n += 1
        save(allx)
    return n


def counts() -> dict:
    out: dict[str, dict] = {}
    for d in load():
        c = out.setdefault(d["cat"], {})
        c[d["status"]] = c.get(d["status"], 0) + 1
    return out
