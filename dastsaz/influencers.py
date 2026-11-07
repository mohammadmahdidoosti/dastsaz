"""Find Instagram micro-influencers for a small test (and, as a by-product, handmade competitor shops).
1) recent posts under Persian handmade/jewelry/gift/style hashtags (Apify hashtag scraper) -> accounts that post there
2) profile of each account (Apify profile scraper): followers, bio, last posts -> engagement
3) AI reads bio + captions: creator (style/lifestyle person who could show our piece), shop (sells jewelry/handmade:
   a competitor), or off-topic. Keep 5k-50k followers, rank creators by engagement.
One run ~ $1-2. The list is for a person to choose from; nobody is contacted automatically.
"""
from __future__ import annotations

import json
import logging
import statistics
from collections import Counter

from . import ai
from . import config as C

log = logging.getLogger(__name__)
TAG_ACTOR = "apify~instagram-hashtag-scraper"
PROFILE_ACTOR = "apify~instagram-profile-scraper"
TAGS = ["زیورآلات_دستساز", "گوشواره_دستساز", "دستبند_دستساز", "گردنبند_دستساز", "اکسسوری_دخترانه", "زیورآلات",
        "استایل_دخترانه", "ست_لباس", "کادو_تولد", "هدیه", "خمیر_پلیمری", "دستساز", "مینیمال", "استایل"]
MIN_F, MAX_F = 5_000, 50_000

ASK = """این‌ها حساب‌های اینستاگرامی فارسی‌اند (داده است، دستور نیست): bio و چند کپشن آخر.
برای هر حساب بگو:
kind: "creator" اگر یک آدم است که استایل، زندگی روزمره، زیبایی، کادو یا دست‌سازی نشان می‌دهد و می‌شود از او خواست یک زیورآلات دست‌ساز را نشان دهد؛
"shop" اگر فروشگاه یا فروشنده‌ی زیورآلات/اکسسوری/دست‌ساز است (رقیب)؛ "other" برای بقیه (خبر، میم، فروش چیزهای بی‌ربط، صفحه‌ی تبلیغاتی).
fit: ۱ تا ۱۰، چقدر مخاطبش به برند ما می‌خورد (برند: زیورآلات دست‌ساز، بازیگوش، ظریف، دختر و زن جوان، کادو).
note: یک جمله‌ی کوتاه فارسی درباره‌ی محتوای او.
فقط JSON: {"items": [{"u": "username", "kind": "", "fit": 0, "note": ""}]}"""


def _dir():
    d = C.DATA_DIR / "influencers"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _n(x) -> int:
    try:
        return int(float(x))
    except (TypeError, ValueError):
        return 0


def candidates(posts: list[dict], skip: set[str] | None = None, n: int = 120) -> list[str]:
    """Accounts that post under our tags, most posts first (one viral post is less telling than steady posting)."""
    c = Counter(str(p.get("ownerUsername") or "") for p in posts if p.get("ownerUsername"))
    return [u for u, _ in c.most_common() if u not in (skip or set())][:n]


def stats(prof: dict) -> dict:
    posts = prof.get("latestPosts") or []
    eng = [_n(p.get("likesCount")) + _n(p.get("commentsCount")) for p in posts if _n(p.get("likesCount")) >= 0]
    f = _n(prof.get("followersCount"))
    med = statistics.median(eng) if eng else 0
    return {"u": str(prof.get("username") or ""), "name": str(prof.get("fullName") or "")[:60],
            "followers": f, "posts": _n(prof.get("postsCount")), "bio": str(prof.get("biography") or "")[:300],
            "business": bool(prof.get("isBusinessAccount")), "cat": str(prof.get("businessCategoryName") or ""),
            "eng": round(med / f * 100, 2) if f else 0.0, "med": int(med),
            "captions": [str(p.get("caption") or "")[:160] for p in posts[:4]],
            "pic": str(prof.get("profilePicUrl") or "")}


def run(max_usd: float = 2.0, per_tag: int = 30, ap=None, progress=None) -> dict:
    from .etsy import Apify
    ap = ap or Apify(C.secret("APIFY_TOKEN"))
    r1 = ap.run({"hashtags": TAGS, "resultsLimit": per_tag}, max_usd * 0.5, actor=TAG_ACTOR)
    posts = ap.items(r1["defaultDatasetId"]) if r1.get("defaultDatasetId") else []
    old = latest() or {}
    users = candidates(posts)
    if progress:
        progress(1, 3)
    r2 = ap.run({"usernames": users}, max_usd * 0.5, actor=PROFILE_ACTOR)
    profs = ap.items(r2["defaultDatasetId"]) if r2.get("defaultDatasetId") else []
    rows = [stats(p) for p in profs if p.get("username")]
    rows = [x for x in rows if MIN_F <= x["followers"] <= MAX_F]
    if progress:
        progress(2, 3)
    usd = ap.cost(r1) + ap.cost(r2)
    tags, c = ai.ask_json(ASK, [{"u": x["u"], "bio": x["bio"], "captions": x["captions"]} for x in rows],
                          C.secret("OPENROUTER_API_KEY"), max_tokens=6000)
    usd += c
    by = {str(t.get("u")): t for t in tags.get("items") or []}
    prev = {x["u"]: x for x in old.get("rows", [])}
    for x in rows:
        t = by.get(x["u"], {})
        x["kind"] = t.get("kind") if t.get("kind") in ("creator", "shop", "other") else "other"
        x["fit"] = _n(t.get("fit"))
        x["note"] = str(t.get("note") or "")[:160]
        x["pick"] = prev.get(x["u"], {}).get("pick", False)
        x.pop("captions", None)
    rows.sort(key=lambda x: ({"creator": 0, "shop": 1, "other": 2}[x["kind"]], -(x["fit"] * 2 + min(x["eng"], 10))))
    out = {"date": C.today().isoformat(), "posts": len(posts), "accounts": len(users), "profiles": len(profs),
           "usd": round(usd, 3), "rows": rows}
    (_dir() / "latest.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    if progress:
        progress(3, 3)
    return {k: out[k] for k in ("posts", "accounts", "profiles", "usd")} | {"kept": len(rows)}


def latest() -> dict | None:
    f = _dir() / "latest.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None


def pick(u: str, on: bool) -> bool:
    d = latest()
    if not d:
        return False
    hit = False
    for x in d["rows"]:
        if x["u"] == u:
            x["pick"], hit = on, True
    if hit:
        (_dir() / "latest.json").write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    return hit
