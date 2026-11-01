"""One trend report, step by step. Each step saves its result in DATA_DIR/runs/<name>/, so a run that is
cut (restart, deploy) continues from the last finished step instead of paying again."""
from __future__ import annotations

import csv
import datetime as dt
import json
import logging
from pathlib import Path
from zoneinfo import ZoneInfo

from . import analyze as A
from . import basalam, costs, digikala, etsy, guard, makers, metals, occasions, report, reviews, suggest, trends
from . import opportunities as O
from . import config as C

log = logging.getLogger(__name__)
CSV_COLS = ["source", "id", "name_fa", "title", "type", "style", "material", "color", "personalized", "motif",
            "stone", "price_usd", "price_toman", "bought_24h", "in_cart", "reviews", "rating", "sales_week",
            "sales_total", "shop", "shop_city", "query", "tags", "materials", "url", "image", "is_jewelry"]


def run_dir(name: str) -> Path:
    d = C.DATA_DIR / "runs" / name
    d.mkdir(parents=True, exist_ok=True)
    return d


def _load(p: Path):
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def _save(p: Path, data) -> None:
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    tmp.replace(p)


def run(name: str, status=lambda **k: None, only: str = "") -> Path:
    """status(step=, done=, total=, note=) is called to show progress. only: 'basalam' to skip Etsy."""
    d = run_dir(name)
    n = C.TOP_N

    def step(s, note=""):
        status(step=s, done=0, total=0, note=note)

    # 1. Basalam (slow, from our server)
    bas = _load(d / "basalam_raw.json")
    if bas is None:
        step("wait", "بررسی اینکه کراولر کاروان صنعت آزاد باشد")
        guard.wait_free(on_wait=lambda why: step("wait", why))
        step("basalam", "خواندن آرام پرفروش‌های باسلام")
        bas = basalam.fetch(progress=lambda i, t: status(step="basalam", done=i, total=t, note=""))
        _save(d / "basalam_raw.json", bas)

    # 1b. Digikala (slow, from our server; best-seller order, no sales numbers)
    dkr = _load(d / "digikala_raw.json")
    if dkr is None and C.DIGIKALA:
        step("digikala", "خواندن آرام پرفروش‌های دیجی‌کالا")
        try:
            dkr = digikala.fetch(progress=lambda i, t: status(step="digikala", done=i, total=t, note=""))
        except Exception as e:  # noqa: BLE001 - Digikala is extra: the report goes on without it
            log.warning("digikala skipped: %s", e)
            dkr = []
        _save(d / "digikala_raw.json", dkr)
    dkr = dkr or []

    # 2. Etsy (on Apify's servers)
    ets = _load(d / "etsy_raw.json")
    if ets is None and only != "basalam":
        step("etsy", "دریافت پرفروش‌های اتسی از Apify")
        ets = etsy.fetch(C.secret("APIFY_TOKEN"),
                         progress=lambda i, t: status(step="etsy", done=i, total=t, note=""),
                         on_cost=lambda q, usd, st: costs.add(d, "اتسی (Apify)", 1, usd, f"{q} {st}"))
        _save(d / "etsy_raw.json", ets)
    ets = ets or []

    # 3. AI: translate + classify the top n of each
    cls = _load(d / "classified.json")
    if cls is None:
        step("ai", "ترجمه و دسته‌بندی سبک‌ها با هوش مصنوعی")
        pick = A.top(ets, n) + A.top(bas, n)
        cls, usd = A.classify_all(pick, C.secret("OPENROUTER_API_KEY"),
                                  progress=lambda i, t: status(step="ai", done=i, total=t, note=""))
        costs.add(d, "هوش مصنوعی (عکس و متن)", len(pick), usd)
        _save(d / "classified.json", cls)

    cdk = _load(d / "classified_dk.json")
    if cdk is None:
        pick_dk = A.top(dkr, n)
        if pick_dk:
            step("ai", "ترجمه و دسته‌بندی دیجی‌کالا")
            cdk, usd = A.classify_all(pick_dk, C.secret("OPENROUTER_API_KEY"),
                                      progress=lambda i, t: status(step="ai", done=i, total=t, note=""))
            costs.add(d, "هوش مصنوعی دیجی‌کالا", len(pick_dk), usd)
        else:
            cdk = []
        _save(d / "classified_dk.json", cdk)
    k = A.top(cdk, n)
    kj = [x for x in k if x.get("is_jewelry", True)]
    e = A.top([x for x in cls if x["source"] == "etsy"], n)
    b = A.top([x for x in cls if x["source"] == "basalam"], n)
    ej = [x for x in e if x.get("is_jewelry", True)]
    bj = [x for x in b if x.get("is_jewelry", True)]

    # 4. opportunity finder: slow extra Basalam searches around promising motifs / Etsy trends
    opps = _load(d / "opportunities.json")
    if opps is None:
        step("expand", "فرصت‌یابی: جست‌وجوهای تکمیلی آرام در باسلام")
        opps = O.expand(ej, bj, progress=lambda i, t: status(step="expand", done=i, total=t, note=""))
        _save(d / "opportunities.json", opps)
    if C.DIGIKALA and any("dk_match" not in o for o in opps):
        step("expand", "فرصت‌یابی: همان جست‌وجوها در دیجی‌کالا")
        try:
            O.add_digikala(opps, progress=lambda i, t: status(step="expand", done=i, total=t, note="دیجی‌کالا"))
        except Exception as e:  # noqa: BLE001
            log.warning("digikala expand skipped: %s", e)
        _save(d / "opportunities.json", opps)
        (d / "testlist.json").unlink(missing_ok=True)       # the list is chosen again with Digikala signals
    opps = O.relabel(opps)
    tl = _load(d / "testlist.json")
    if tl is None:
        step("testlist", "ساختن لیست آزمایش هفتگی")
        tl, usd = O.test_list(opps, ej, C.secret("OPENROUTER_API_KEY"))
        if usd:
            costs.add(d, "لیست آزمایش (هوش مصنوعی)", len(tl), usd)
        _save(d / "testlist.json", tl)
    # 4b. Google Trends (Iran): timing + rising searches; new jewelry ideas become extra opportunity searches
    tr = _load(d / "trends.json")
    if tr is None and C.TRENDS:
        step("trends", "گوگل ترندز ایران")
        try:
            tr = trends.fetch(C.secret("APIFY_TOKEN"), trends.keywords(tl),
                              on_cost=lambda n, usd, st: costs.add(d, "گوگل ترندز (Apify)", n, usd, st))
        except Exception as e:  # noqa: BLE001 - extra: the report goes on without it
            log.warning("trends skipped: %s", e)
            tr = []
        _save(d / "trends.json", tr)
    tr = tr or []
    if tr and not any(o["source"] == "google" for o in opps):
        ideas = trends.new_ideas(tr, {o["q"] for o in opps})
        if ideas:
            step("expand", "جست‌وجوهای در حال رشد گوگل در باسلام و دیجی‌کالا")
            try:
                extra = O.run_queries(O.google_queries(ideas),
                                      progress=lambda i, t: status(step="expand", done=i, total=t, note="گوگل"))
                extra = [x for x in extra if x.get("match", 0) >= 3]   # Basalam must really have this design
                if C.DIGIKALA:
                    O.add_digikala(extra)
                opps = O.relabel(opps + extra)
                _save(d / "opportunities.json", opps)
                tl, usd = O.test_list(opps, ej, C.secret("OPENROUTER_API_KEY"))
                if usd:
                    costs.add(d, "لیست آزمایش (هوش مصنوعی)", len(tl), usd)
                _save(d / "testlist.json", tl)
            except Exception as e:  # noqa: BLE001
                log.warning("google ideas skipped: %s", e)
    # 4c. What people type on Digikala: suggestions that are designs become extra opportunity searches
    sug = _load(d / "suggestions.json")
    if sug is None and C.DIGIKALA:
        step("suggest", "پیشنهادهای جست‌وجوی دیجی‌کالا")
        try:
            sug = suggest.fetch(progress=lambda i, t: status(step="suggest", done=i, total=t, note=""))
        except Exception as e:  # noqa: BLE001
            log.warning("suggestions skipped: %s", e)
            sug = {}
        _save(d / "suggestions.json", sug)
    sug = sug or {}
    if sug and not any(o["source"] == "suggest" for o in opps):
        ideas = suggest.ideas(sug, {o["q"] for o in opps})
        if ideas:
            step("expand", "جست‌وجوهای پرتکرار مردم در باسلام و دیجی‌کالا")
            try:
                extra = O.run_queries(O.google_queries(ideas, "suggest"),
                                      progress=lambda i, t: status(step="expand", done=i, total=t, note="پیشنهادها"))
                extra = [x for x in extra if x.get("match", 0) >= 3]
                for x in extra:
                    x["typed"] = sug.get("counts", {}).get(x["q"], 0)
                if C.DIGIKALA:
                    O.add_digikala(extra)
                opps = O.relabel(opps + extra)
                _save(d / "opportunities.json", opps)
                tl, usd = O.test_list(opps, ej, C.secret("OPENROUTER_API_KEY"))
                if usd:
                    costs.add(d, "لیست آزمایش (هوش مصنوعی)", len(tl), usd)
                _save(d / "testlist.json", tl)
                (d / "reviews.json").unlink(missing_ok=True)
            except Exception as e:  # noqa: BLE001
                log.warning("suggestion ideas skipped: %s", e)

    # 4d. buyers' reviews of each test design's best-sellers (complaints = what to do better)
    rv = _load(d / "reviews.json")
    if rv is None and tl:
        step("reviews", "خواندن نظر خریداران")
        try:
            raw = reviews.collect(tl, progress=lambda i, t: status(step="reviews", done=i, total=t, note=""))
            rv, usd = reviews.summarize(tl, raw, C.secret("OPENROUTER_API_KEY"))
            if usd:
                costs.add(d, "خلاصه‌ی نظرها (هوش مصنوعی)", len(tl), usd)
        except Exception as e:  # noqa: BLE001
            log.warning("reviews skipped: %s", e)
            rv = {}
        _save(d / "reviews.json", rv)
    rv = rv or {}

    # 4e. possible makers among the Basalam booths
    mk_ = _load(d / "makers.json")
    if mk_ is None:
        top_shops = makers.shops(bas)
        if top_shops:
            step("makers", "پیدا کردن سازنده‌ها در باسلام")
            try:
                mk_ = makers.details(top_shops, progress=lambda i, t: status(step="makers", done=i, total=t, note=""))
            except Exception as e:  # noqa: BLE001
                log.warning("makers skipped: %s", e)
                mk_ = []
        else:
            mk_ = []             # an older run without booth ids
        _save(d / "makers.json", mk_)

    # 4f. today's metal prices (always fresh) and the coming occasions
    mt = metals.fetch()
    if mt:
        _save(d / "metals.json", mt)
    else:
        mt = _load(d / "metals.json") or {}
    occ = occasions.upcoming(test_list=tl)

    with (d / "opportunities.csv").open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["جست‌وجو", "برچسب‌ها", "فروش این هفته (۱۰ پرفروش)", "فروش کل (۱۰ پرفروش)",
                    "تعداد محصول در باسلام", "اوج (٪)", "قیمت ارزان", "قیمت گران", "تعداد محصول در دیجی‌کالا",
                    "همین طرح در ۲۰ پرفروش دیجی‌کالا", "امتیازدهنده‌های همین طرح در دیجی‌کالا", "قیمت میانه دیجی‌کالا", "امتیاز", "دلیل"])
        for o in sorted(opps, key=lambda o: -o["score"]):
            w.writerow([o["q"], "، ".join(o["labels"]), o["week"], o["alltime"], o["supply"],
                        round(o["momentum"] * 100), o["price_low"], o["price_high"], o.get("dk_match"),
                        o.get("dk_reviews"), o.get("dk_price_median"), o["score"], o["why"]])

    # 5. report
    step("report", "ساختن گزارش")
    with (d / "products.csv").open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, CSV_COLS, extrasaction="ignore")
        w.writeheader()
        w.writerows(e + b + k)
    when = dt.datetime.now(ZoneInfo(C.TIMEZONE)).strftime("%Y-%m-%d %H:%M")
    return report.build(d, name, e, b, C.secret("OPENROUTER_API_KEY"),
                        lambda s, u, usd: costs.add(d, s, u, usd), when, opps=opps, tl=tl, dk=kj, tr=tr,
                        extra={"suggest": sug, "reviews": rv, "makers": mk_, "metals": mt, "occasions": occ})


def runs() -> list[dict]:
    base = C.DATA_DIR / "runs"
    out = []
    if base.exists():
        for d in sorted(base.iterdir(), reverse=True):
            if d.is_dir():
                out.append({"name": d.name, "report": (d / "report.html").exists(),
                            "usd": costs.summary(d)["usd"]})
    return out
