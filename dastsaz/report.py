"""Builds the Persian trend report (one self-contained HTML page) from the classified products."""
from __future__ import annotations

import html
import json
import logging
import statistics
from collections import Counter
from pathlib import Path

import requests

from . import analyze as A
from . import config as C

log = logging.getLogger(__name__)
FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def fa(n, dec: int = 0) -> str:
    if n is None or n == "":
        return "—"
    s = f"{n:,.{dec}f}" if isinstance(n, (int, float)) else str(n)
    return s.translate(FA_DIGITS).replace(",", "٬")


def shares(items: list[dict], field: str) -> dict[str, float]:
    c = Counter(x.get(field) or "سایر" for x in items)
    n = sum(c.values()) or 1
    return {k: v * 100 / n for k, v in c.items()}


def compare(etsy: list[dict], bas: list[dict], field: str, order: list[str]) -> list[dict]:
    e, b = shares(etsy, field), shares(bas, field)
    rows = [{"name": k, "etsy": e.get(k, 0.0), "basalam": b.get(k, 0.0), "gap": e.get(k, 0.0) - b.get(k, 0.0)}
            for k in order if e.get(k) or b.get(k)]
    return sorted(rows, key=lambda r: -(r["etsy"] + r["basalam"]))


def price_stats(vals: list[float]) -> dict | None:
    v = sorted(x for x in vals if x)
    if len(v) < 3:
        return None
    q = statistics.quantiles(v, n=4)
    return {"n": len(v), "low": q[0], "median": statistics.median(v), "high": q[2]}


def prices_by_type(etsy, bas) -> list[dict]:
    rows = []
    for t in A.TYPES:
        e = price_stats([x["price_usd"] for x in etsy if x["type"] == t])
        b = price_stats([x["price_toman"] for x in bas if x["type"] == t])
        if e or b:
            rows.append({"type": t, "etsy": e, "basalam": b})
    return rows


def counts(items, field, n=12) -> list[tuple[str, int]]:
    return Counter(x[field] for x in items if x.get(field)).most_common(n)


def stats(etsy: list[dict], bas: list[dict]) -> dict:
    return {
        "n_etsy": len(etsy), "n_basalam": len(bas),
        "type": compare(etsy, bas, "type", A.TYPES), "style": compare(etsy, bas, "style", A.STYLES),
        "material": compare(etsy, bas, "material", A.MATERIALS), "color": compare(etsy, bas, "color", A.COLORS),
        "prices": prices_by_type(etsy, bas),
        "motif_etsy": counts(etsy, "motif"), "motif_basalam": counts(bas, "motif"),
        "stone_etsy": counts(etsy, "stone", 8), "stone_basalam": counts(bas, "stone", 8),
        "personal_etsy": sum(1 for x in etsy if x["personalized"]) * 100 / (len(etsy) or 1),
        "personal_basalam": sum(1 for x in bas if x["personalized"]) * 100 / (len(bas) or 1),
    }


INSIGHT_ASK = """تو تحلیلگر بازار جواهرات دست‌ساز هستی. صاحب یک فروشگاه ایرانی می‌خواهد با تولیدکننده‌های ایرانی
(جواهرساز، نقره‌کار، صنعتگر) صحبت کند تا محصولات ترند را بسازند و بفروشد. آمار زیر مقایسه‌ی پرفروش‌های Etsy
(بازار جهانی) و باسلام (بازار ایران) است. «gap» یعنی سهم در اتسی منهای سهم در باسلام (درصد).
در ۶ تا ۸ بند کوتاه، به فارسی ساده و بدون اصطلاح فنی، بگو:
- کدام سبک/جنس/رنگ در اتسی داغ است ولی در باسلام کم است (فرصت)
- چه چیزی در باسلام خوب می‌فروشد (بازار آماده)
- چه بازه‌ی قیمتی منطقی است
- با تولیدکننده دقیقاً درباره‌ی ساخت چه چیزی صحبت کند
فقط JSON بده: {"points": ["...", "..."]}
آمار:
"""


def insights(st: dict, key: str) -> tuple[list[str], float]:
    if not key:
        return [], 0.0
    slim = {k: st[k] for k in ("style", "material", "color", "personal_etsy", "personal_basalam",
                               "motif_etsy", "motif_basalam")}
    slim["prices"] = st["prices"]
    body = {"model": C.AI_MODEL, "max_tokens": 4000, "temperature": 0.3, "reasoning": {"enabled": False},
            "messages": [{"role": "user", "content": INSIGHT_ASK + json.dumps(slim, ensure_ascii=False, default=round)}]}
    try:
        r = requests.post(A.OPENROUTER, json=body, timeout=120, headers={
            "Authorization": f"Bearer {key}", "Content-Type": "application/json", "X-Title": "Dastsaz trends"})
        j = r.json()
        txt = ((j.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
        import re
        m = re.search(r"\{.*\}", txt, re.S)
        pts = json.loads(m.group(0)).get("points", []) if m else []
        return [str(p) for p in pts][:10], float((j.get("usage") or {}).get("cost") or 0)
    except Exception as e:  # noqa: BLE001
        log.warning("insights failed: %s", e)
        return [], 0.0


# ------------------------------------------------------------------ HTML

CSS = """
*{box-sizing:border-box}body{margin:0;font-family:Vazirmatn,Tahoma,sans-serif;background:#faf7f2;color:#2b2622;line-height:1.8}
.wrap{max-width:1150px;margin:auto;padding:24px 16px 60px}
h1{font-size:28px;margin:0 0 4px}h2{font-size:21px;margin:40px 0 12px;border-bottom:2px solid #e6dccd;padding-bottom:6px}
.sub{color:#7a6e63;font-size:14px}.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin:18px 0}
.card{background:#fff;border:1px solid #ece3d6;border-radius:12px;padding:14px}.card b{display:block;font-size:24px}
.ins{background:#fff;border-right:4px solid #b8860b;border-radius:10px;padding:14px 20px}.ins li{margin:6px 0}
table{width:100%;border-collapse:collapse;background:#fff;border-radius:10px;overflow:hidden;font-size:14px;margin-bottom:10px}
th,td{padding:7px 10px;border-bottom:1px solid #f0e9df;text-align:right}th{background:#f4ede3;font-weight:600}
.bar{display:inline-block;height:9px;border-radius:5px;vertical-align:middle;margin-left:6px}
.e{background:#d96c3f}.b{background:#3f8f7a}.gp{color:#b04a1e;font-weight:600}.gn{color:#3f8f7a}
.two{display:grid;grid-template-columns:1fr 1fr;gap:18px}@media(max-width:760px){.two{grid-template-columns:1fr}}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(170px,1fr));gap:12px}
.p{background:#fff;border:1px solid #ece3d6;border-radius:10px;overflow:hidden;font-size:13px}
.p img{width:100%;aspect-ratio:1;object-fit:cover;background:#eee;display:block}.p div{padding:8px}
.p a{color:inherit;text-decoration:none}.tag{display:inline-block;background:#f4ede3;border-radius:6px;padding:0 6px;margin:2px 0 0 2px;font-size:11px}
.legend span{margin-left:14px;font-size:13px}.muted{color:#8a7f74;font-size:12px}
"""


def _bar(v, cls):
    return f'<span class="bar {cls}" style="width:{max(2, v * 1.6):.0f}px"></span>{fa(v)}٪'


def _cmp_table(rows, title):
    out = [f"<h3>{title}</h3><table><tr><th></th><th>اتسی</th><th>باسلام</th><th>فاصله</th></tr>"]
    for r in rows:
        g = round(r["gap"])
        gcls = "gp" if g >= 5 else ("gn" if g <= -5 else "")
        sign = "+" if g > 0 else ""
        out.append(f"<tr><td>{html.escape(r['name'])}</td><td>{_bar(r['etsy'], 'e')}</td>"
                   f"<td>{_bar(r['basalam'], 'b')}</td><td class='{gcls}'>{sign}{fa(g)}</td></tr>")
    out.append("</table>")
    return "".join(out)


def _price_table(rows):
    out = ["<table><tr><th>نوع</th><th>اتسی (دلار) — ارزان / میانه / گران</th><th>همان به تومان (میانه)</th>"
           "<th>باسلام (تومان) — ارزان / میانه / گران</th></tr>"]
    for r in rows:
        e, b = r["etsy"], r["basalam"]
        et = f"{fa(e['low'])} / <b>{fa(e['median'])}</b> / {fa(e['high'])}" if e else "—"
        etm = fa(round(e["median"] * C.USD_TOMAN, -3)) if e else "—"
        bt = f"{fa(round(b['low'], -3))} / <b>{fa(round(b['median'], -3))}</b> / {fa(round(b['high'], -3))}" if b else "—"
        out.append(f"<tr><td>{r['type']}</td><td>{et}</td><td>{etm}</td><td>{bt}</td></tr>")
    out.append("</table><p class='muted'>«ارزان» و «گران» یعنی یک‌چهارم پایین و بالای قیمت‌ها؛ "
               f"تبدیل دلار با نرخ {fa(C.USD_TOMAN)} تومان.</p>")
    return "".join(out)


def _list(pairs):
    return "".join(f"<span class='tag'>{html.escape(k)} ({fa(v)})</span> " for k, v in pairs) or "—"


def _gallery(items, n=40):
    out = ["<div class='grid'>"]
    for p in items[:n]:
        sig = []
        if p["source"] == "etsy":
            if p.get("bought_24h"):
                sig.append(f"{fa(p['bought_24h'])} خرید در ۲۴ ساعت")
            if p.get("in_cart"):
                sig.append(f"در سبد {fa(p['in_cart'])} نفر")
            if p.get("reviews"):
                sig.append(f"{fa(p['reviews'])} نظر برای فروشگاه")
            price = f"{fa(p['price_usd'], 2)} دلار" if p.get("price_usd") else ""
        else:
            if p.get("sales_week"):
                sig.append(f"{fa(p['sales_week'])} فروش این هفته")
            sig.append(f"{fa(p.get('sales_total'))} فروش کل")
            price = f"{fa(round(p['price_toman'] or 0, -2))} تومان" if p.get("price_toman") else ""
        name = html.escape(p.get("name_fa") or p["title"])
        img = html.escape(p.get("image") or "")
        out.append(f"<div class='p'><a href='{html.escape(p['url'])}' target='_blank' rel='noopener'>"
                   f"<img loading='lazy' src='{img}' alt=''><div><b>{name}</b><br>{price}<br>"
                   f"<span class='muted'>{' · '.join(sig)}</span><br>"
                   f"<span class='tag'>{p['style']}</span><span class='tag'>{p['material']}</span>"
                   f"<span class='tag'>{p['color']}</span></div></a></div>")
    out.append("</div>")
    return "".join(out)


def render(name: str, etsy: list[dict], bas: list[dict], st: dict, points: list[str], cost: dict,
           when: str) -> str:
    ins = "".join(f"<li>{html.escape(p)}</li>" for p in points) or "<li>جمع‌بندی هوش مصنوعی ساخته نشد.</li>"
    steps = "، ".join(f"{k}: {fa(v['usd'], 3)}$" for k, v in cost.get("steps", {}).items())
    return f"""<!DOCTYPE html><html lang="fa" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>گزارش ترند دست‌ساز — {html.escape(name)}</title>
<style>{CSS}</style></head><body><div class="wrap">
<h1>گزارش ترند جواهرات</h1><div class="sub">{html.escape(when)} · اتسی (بازار جهانی) در برابر باسلام (بازار ایران)</div>
<div class="cards"><div class="card">پرفروش اتسی<b>{fa(st['n_etsy'])}</b></div>
<div class="card">پرفروش باسلام<b>{fa(st['n_basalam'])}</b></div>
<div class="card">شخصی‌سازی‌شده در اتسی<b>{fa(st['personal_etsy'])}٪</b></div>
<div class="card">شخصی‌سازی‌شده در باسلام<b>{fa(st['personal_basalam'])}٪</b></div>
<div class="card">هزینه‌ی این گزارش<b>{fa(cost.get('usd', 0), 2)} $</b></div></div>
<h2>جمع‌بندی برای صحبت با تولیدکننده</h2><ul class="ins">{ins}</ul>
<p class="legend"><span><span class="bar e" style="width:20px"></span>اتسی</span>
<span><span class="bar b" style="width:20px"></span>باسلام</span>
<span class="gp">قرمز = در اتسی خیلی بیشتر (فرصت)</span><span class="gn">سبز = در باسلام بیشتر</span></p>
<h2>سبک، جنس و رنگ (درصد از پرفروش‌ها)</h2>
<div class="two"><div>{_cmp_table(st['style'], 'سبک')}</div><div>{_cmp_table(st['material'], 'جنس')}</div>
<div>{_cmp_table(st['color'], 'رنگ')}</div></div>
<p class="muted">سهم «نوع» (گردنبند، گوشواره و…) نشان داده نشده، چون برای هر نوع به یک اندازه جست‌وجو کرده‌ایم و سهمش ساخته‌ی روش ماست، نه ترند.</p>
<h2>بازه‌ی قیمت</h2>{_price_table(st['prices'])}
<h2>نقش‌ها و سنگ‌های پرتکرار</h2>
<div class="two"><div><h3>اتسی</h3><p>نقش‌ها: {_list(st['motif_etsy'])}</p><p>سنگ‌ها: {_list(st['stone_etsy'])}</p></div>
<div><h3>باسلام</h3><p>نقش‌ها: {_list(st['motif_basalam'])}</p><p>سنگ‌ها: {_list(st['stone_basalam'])}</p></div></div>
<h2>۴۰ پرفروش اول اتسی</h2>{_gallery(etsy)}
<h2>۴۰ پرفروش اول باسلام</h2>{_gallery(bas)}
<p class="muted" style="margin-top:30px">پرفروش اتسی بر اساس ترتیب خود اتسی (که پرفروش‌ها را جلو می‌آورد) و تعداد نظرهای فروشگاه؛
باسلام بر اساس فروش این هفته و فروش کل. سبک و جنس و رنگ را هوش مصنوعی از روی عکس و عنوان تشخیص داده و ممکن است چند مورد اشتباه باشد.
هزینه به تفکیک: {steps or '—'}</p>
</div></body></html>"""


def build(run_dir: Path, name: str, etsy: list[dict], bas: list[dict], key: str, cost_add, when: str) -> Path:
    etsy = [x for x in etsy if x.get("is_jewelry", True)]
    bas = [x for x in bas if x.get("is_jewelry", True)]
    st = stats(etsy, bas)
    points, usd = insights(st, key)
    if usd:
        cost_add("جمع‌بندی", 1, usd)
    from . import costs
    page = render(name, etsy, bas, st, points, costs.summary(run_dir), when)
    (run_dir / "stats.json").write_text(json.dumps({**st, "points": points}, ensure_ascii=False, default=str,
                                                   indent=1), encoding="utf-8")
    p = run_dir / "report.html"
    p.write_text(page, encoding="utf-8")
    return p
