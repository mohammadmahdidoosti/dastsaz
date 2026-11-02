"""The report page (one self-contained HTML file, served by the app with the bundled Vazirmatn font).

Look: a jeweller's tray. Three materials stand for the three markets everywhere on the page:
gold = Etsy, turquoise (فیروزه) = Basalam, lapis (لاجورد) = Digikala. Ink on porcelain for the rest.
"""
from __future__ import annotations

import html
import math
from urllib.parse import quote

from . import config as C

FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
JMONTHS = ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور", "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"]
MARKET = {"etsy": ("اتسی", "gold"), "basalam": ("باسلام", "turq"), "digikala": ("دیجی‌کالا", "lapis"),
          "google": ("گوگل", "ink")}
LAB_CLS = {"تقاضای زیاد، رقیب کم": "good", "در حال اوج": "hot", "ترند جهانی، تازه در ایران": "hot",
           "در دیجی‌کالا کم‌رقیب": "good", "در دیجی‌کالا هم پرفروش": "", "جست‌وجوی تازه در گوگل": "",
           "بازار خالی (آزمایش جسورانه)": "dim", "پرفروش ولی ضعیف": "", "رقابت سنگین": "dim",
           "در جست‌وجوی مردم": "good"}
def E(t) -> str:
    return html.escape(str(t))


def P(t) -> str:
    """AI-written text: Persian digits and decimal sign, then escaped."""
    import re as _re
    t = _re.sub(r"(?<=\d)\.(?=\d)", "٫", str(t or ""))
    t = _re.sub(r"(?<=\d),(?=\d{3})", "٬", t)
    return html.escape(t.translate(FA_DIGITS))


def fa(n, dec: int = 0) -> str:
    if n is None or n == "":
        return "—"
    s = f"{n:,.{dec}f}" if isinstance(n, (int, float)) else str(n)
    return s.replace(",", "٬").replace(".", "٫").translate(FA_DIGITS)


def toman(n) -> str:
    if not n:
        return "—"
    if n >= 1_000_000:
        return f"{fa(n / 1_000_000, 1).replace('٫۰', '')} میلیون"
    return f"{fa(round(n / 1000))} هزار"


def jalali(date: str) -> str:
    """'2026-12-15' -> '۲۴ آذر ۱۴۰۵'; anything else is returned as is."""
    try:
        gy, gm, gd = (int(x) for x in str(date)[:10].split("-"))
    except ValueError:
        return str(date or "")
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    gy2 = gy + 1 if gm > 2 else gy
    days = 355666 + 365 * gy + (gy2 + 3) // 4 - (gy2 + 99) // 100 + (gy2 + 399) // 400 + gd + g_d_m[gm - 1]
    jy = -1595 + 33 * (days // 12053)
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365
    jm = 1 + days // 31 if days < 186 else 7 + (days - 186) // 30
    jd = 1 + (days % 31 if days < 186 else (days - 186) % 30)
    return f"{fa(jd)} {JMONTHS[jm - 1]} {str(jy).translate(FA_DIGITS)}"


CSS = """
@font-face{font-family:Vazirmatn;src:url(/static/vazirmatn.woff2) format('woff2');font-weight:100 900;font-display:swap}
:root{--ink:#1d2433;--soft:#5b6476;--paper:#f4f5f2;--card:#fff;--line:#dfe2dc;--gold:#b0822a;--gold-l:#f3e7cc;
--turq:#13877f;--turq-l:#d5eeeb;--lapis:#2f4b85;--lapis-l:#dde4f3;--rose:#a43f55;--rose-l:#f6e1e6}
*{box-sizing:border-box}html{scroll-behavior:smooth}
body{margin:0;background:var(--paper);color:var(--ink);font:400 15px/1.85 Vazirmatn,Tahoma,sans-serif;
font-feature-settings:"ss01"}
a{color:var(--lapis)}a:focus-visible,summary:focus-visible{outline:2px solid var(--gold);outline-offset:2px}
.wrap{max-width:1120px;margin:auto;padding:0 20px}
.bar-top{position:sticky;top:0;z-index:5;background:rgba(244,245,242,.94);backdrop-filter:blur(6px);
border-bottom:1px solid var(--line)}
.bar-top .wrap{display:flex;gap:22px;align-items:center;height:52px;overflow-x:auto;white-space:nowrap}
.brand{font-weight:800;font-size:18px;letter-spacing:-.2px;margin-left:12px}
.bar-top a{color:var(--soft);text-decoration:none;font-size:14px}.bar-top a:hover{color:var(--ink)}
.hero{background:var(--lapis);color:#fff;padding:44px 0 50px;position:relative;overflow:hidden}
.hero:before{content:"";position:absolute;inset:auto -80px -120px auto;width:340px;height:340px;border-radius:50%;
border:2px solid rgba(255,255,255,.12);box-shadow:0 0 0 26px rgba(255,255,255,.04)}
.hero .wrap{display:grid;grid-template-columns:1.35fr 1fr;gap:40px;align-items:center}
.hero .date{color:#c9d3ea;font-size:14px}
.hero h1{font-size:34px;line-height:1.45;font-weight:800;margin:10px 0 14px;letter-spacing:-.3px}
.hero p{color:#dfe5f3;margin:0;max-width:60ch}
.markets{display:flex;gap:18px;margin-top:22px;flex-wrap:wrap;font-size:14px;color:#dfe5f3}
.markets b{font-size:22px;color:#fff;display:block;font-weight:800}
.pick{background:#fff;color:var(--ink);border-radius:14px;padding:14px;display:grid;grid-template-columns:120px 1fr;
gap:14px;align-items:center;box-shadow:0 18px 40px rgba(10,20,50,.28)}
.pick img{width:120px;height:120px;object-fit:cover;border-radius:10px;background:#eee}
.pick .k{font-size:13px;color:var(--gold);font-weight:700}.pick h3{margin:2px 0 6px;font-size:19px;line-height:1.5}
.pick .n{font-size:13px;color:var(--soft)}
section{padding:46px 0 10px}
h2{font-size:24px;font-weight:800;margin:0 0 6px;letter-spacing:-.2px}
.lead{color:var(--soft);margin:0 0 22px;max-width:75ch}
.exec{display:grid;grid-template-columns:1.4fr 1fr;gap:34px}
.finding{padding:14px 0;border-top:1px solid var(--line)}.finding:first-child{border-top:0;padding-top:0}
.finding b{display:block;font-size:16px}.finding span{color:#3a4252}
.todo{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:18px 20px}
.todo h3{margin:0 0 8px;font-size:16px}.todo ol{margin:0;padding-right:20px}.todo li{margin:6px 0}
.todo.risk{border-color:#ead0d7;background:#fff9fa;margin-top:14px}.todo.risk ul{margin:0;padding-right:18px}
.brief{margin-top:22px;background:var(--gold-l);border-radius:12px;padding:16px 20px;color:#4a3a14}
.brief b{display:block;margin-bottom:4px}
.design{display:grid;grid-template-columns:260px 1fr 240px;gap:22px;background:var(--card);border:1px solid var(--line);
border-radius:12px;padding:16px;margin-bottom:14px}
.design .shots{display:grid;grid-template-columns:1fr 1fr;gap:6px}
.design .shots img{width:100%;aspect-ratio:1;object-fit:cover;border-radius:6px;background:#eee;display:block}
.design .shots a{position:relative;display:block}
.design .shots i{position:absolute;bottom:4px;right:4px;font-style:normal;font-size:10px;padding:0 6px;border-radius:4px;
color:#fff}
.i-gold{background:var(--gold)}.i-turq{background:var(--turq)}.i-lapis{background:var(--lapis)}.i-ink{background:var(--ink)}
.design h3{margin:0;font-size:19px;line-height:1.5}.design .rank{color:var(--soft);font-size:13px}
.design .why{color:#3a4252;margin:8px 0}
.labs span{display:inline-block;font-size:12px;border-radius:999px;padding:1px 10px;margin:0 0 4px 4px;
background:#eef0ec;color:#424a59}
.labs .good{background:var(--turq-l);color:#0d625c}.labs .hot{background:var(--gold-l);color:#7a5714}
.labs .dim{background:#eceef0;color:#7a808b}
.ev{font-size:13px;color:var(--soft);margin-top:6px}.ev div{margin:2px 0}
.eco{border-right:1px solid var(--line);padding-right:18px;font-size:14px}
.eco dl{margin:0;display:grid;grid-template-columns:auto 1fr;gap:4px 12px}
.eco dt{color:var(--soft)}.eco dd{margin:0;font-weight:700}
.eco .rk{margin-top:10px;font-size:12px;color:var(--rose)}.eco .rk div{margin:2px 0}
.eco .mt{margin-top:10px;font-size:12px;color:#5b6476;background:#f1f3f7;border-radius:6px;padding:6px 8px}
.ev .rev{margin-top:8px;padding:8px 10px;background:#fff7f0;border-radius:8px;color:#5a4330}
.chips{display:flex;flex-wrap:wrap;gap:6px}.chips span{background:var(--card);border:1px solid var(--line);
border-radius:999px;padding:2px 12px}.chips span b{color:var(--turq);margin-right:4px}
.chips span.tested{border-color:var(--turq);background:var(--turq-l)}
.metal{display:flex;gap:14px;flex-wrap:wrap;margin-bottom:18px}.metal div{background:var(--card);border:1px solid var(--line);
border-radius:10px;padding:10px 16px}.metal b{display:block;font-size:19px}
tr.quiet td{color:var(--soft);background:#f7f7f5}.soon{color:var(--rose);font-weight:700}
.prov{display:flex;gap:8px;flex-wrap:wrap;margin:0 0 12px}.prov span{background:var(--gold-l);border-radius:6px;padding:1px 10px}
.map{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:10px}
.map svg{width:100%;height:auto;display:block}
.legend{display:flex;gap:16px;flex-wrap:wrap;font-size:13px;color:var(--soft);margin-top:8px}
.dot{display:inline-block;width:10px;height:10px;border-radius:50%;margin-left:5px;vertical-align:middle}
.d-gold{background:var(--gold)}.d-turq{background:var(--turq)}.d-lapis{background:var(--lapis)}.d-ink{background:var(--ink)}
.three{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}
.persona{background:var(--card);border-radius:12px;padding:16px 18px;border-top:5px solid}
.persona.gold{border-color:var(--gold)}.persona.turq{border-color:var(--turq)}.persona.lapis{border-color:var(--lapis)}
.persona h3{margin:0 0 6px}.persona p{margin:4px 0;font-size:14px}.persona .big{font-size:22px;font-weight:800}
table{width:100%;border-collapse:collapse;background:var(--card);font-size:14px;border:1px solid var(--line);border-radius:6px}
th,td{padding:8px 10px;border-bottom:1px solid #eceee9;text-align:right;vertical-align:top}
th{font-weight:700;color:#3a4252;background:#f8f9f6}
.cmp td.v{white-space:nowrap;width:24%}
.b{display:inline-block;height:8px;border-radius:4px;vertical-align:middle;margin-left:6px;min-width:2px}
.b-gold{background:var(--gold)}.b-turq{background:var(--turq)}.b-lapis{background:var(--lapis)}
.cols{display:grid;grid-template-columns:1fr 1fr;gap:18px}.cols h3{margin:10px 0 8px;font-size:17px}
.up{color:#0d625c;font-weight:700}.down{color:var(--rose);font-weight:700}
.tag{display:inline-block;background:#eef0ec;border-radius:6px;padding:0 7px;margin:2px 0 2px 3px;font-size:12px}
details{background:var(--card);border:1px solid var(--line);border-radius:10px;margin-bottom:10px}
summary{cursor:pointer;padding:12px 16px;font-weight:700}details[open] summary{border-bottom:1px solid var(--line)}
details .in{padding:14px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:12px}
.p{font-size:13px}.p a{color:inherit;text-decoration:none}.p img{width:100%;aspect-ratio:1;object-fit:cover;
border-radius:8px;background:#eee;display:block;margin-bottom:6px}.p .s{color:var(--soft);font-size:12px}
.muted{color:var(--soft);font-size:13px}
footer{padding:40px 0 60px;color:var(--soft);font-size:13px}
@media(max-width:900px){.hero .wrap,.exec,.design,.three,.cols{grid-template-columns:1fr}
.eco{border-right:0;padding-right:0;border-top:1px solid var(--line);padding-top:10px}.hero h1{font-size:26px}}
@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}}
"""


def _labs(labels):
    return "<div class='labs'>" + "".join(f"<span class='{LAB_CLS.get(l, '')}'>{E(l)}</span>" for l in labels) + "</div>"


def _shots(o):
    imgs = [(x, "turq", "باسلام") for x in (o.get("images") or [])[:2]]
    imgs += [(x, "gold", "اتسی") for x in (o.get("etsy_refs") or [])[:1]]
    imgs += [(x, "lapis", "دیجی‌کالا") for x in (o.get("dk_images") or [])[:1]]
    imgs = imgs[:4]
    return "<div class='shots'>" + "".join(
        f"<a href='{E(x['url'])}' target='_blank' rel='noopener' title='{E(x['title'])}'>"
        f"<img loading='lazy' src='{E(x['src'])}' alt='{E(x['title'])}'><i class='i-{c}'>{m}</i></a>"
        for x, c, m in imgs) + "</div>"


def _design(i: int, o: dict) -> str:
    eco = o.get("eco") or {}
    ev = [f"<div>باسلام: <a href='{E(o.get('basalam_link') or '#')}' target='_blank' rel='noopener'>«{E(o['q'])}»</a> — "
          f"{fa(o['week'])} فروش این هفته در ۱۰ پرفروش، {fa(o['supply'])} محصول رقیب</div>"]
    if "dk_match" in o:
        ev.append(f"<div>دیجی‌کالا: <a href='{E(o.get('dk_link') or '#')}' target='_blank' rel='noopener'>"
                  f"{fa(o['dk_match'])} از ۲۰ پرفروش</a> همین طرح‌اند، {fa(o.get('dk_reviews', 0))} امتیازدهنده</div>")
    rk = "".join(f"<div>{E(r)}</div>" for r in eco.get("risks", []))
    rv = o.get("review") or {}
    if rv.get("n"):
        cm = "، ".join(P(c) for c in rv.get("complaints", [])) or "شکایت تکرارشونده‌ای پیدا نشد"
        better = f"<div><b>نسخه‌ی بهتر ما:</b> {P(rv['improve'])}</div>" if rv.get("improve") else ""
        ev.append(f"<div class='rev'><b>نظر خریداران:</b> {fa(rv['n'])} نظر، {fa(rv.get('low', 0))} ناراضی"
                  f"{('، میانگین ' + fa(rv['avg'], 1) + ' از ۵') if rv.get('avg') else ''}. "
                  f"<b>شکایت‌ها:</b> {cm}{better}</div>")
    metal = f"<div class='mt'>{P(eco['metal'])}</div>" if eco.get("metal") else ""
    return f"""<article class="design">{_shots(o)}
<div><div class="rank">طرح {fa(i)}</div><h3>{E(o.get('name') or o['q'])}</h3>{_labs(o['labels'])}
<p class="why">{P(o.get('brief') or '')}</p><div class="ev"><div>چرا: {E(o['why'])}</div>{''.join(ev)}</div></div>
<div class="eco"><dl><dt>قیمت فروش</dt><dd>{toman(eco.get('retail'))} تومان</dd>
<dt>خرید از سازنده</dt><dd>حداکثر {toman(eco.get('buy_max'))}</dd>
<dt>تعداد آزمایشی</dt><dd>{fa(eco.get('test_qty'))} عدد</dd>
<dt>کجا بفروشید</dt><dd>{E('، '.join(eco.get('channels', [])))}</dd></dl>
{metal}{f"<div class='rk'>{rk}</div>" if rk else ""}</div></article>"""


def _map(opps: list[dict], tl: list[dict], mid: float) -> str:
    pts = [o for o in opps if o.get("supply")]
    if len(pts) < 4:
        return ""
    W, H, PL, PR, PT, PB = 960, 440, 40, 30, 30, 50
    xs = [math.log10(o["supply"] + 10) for o in pts]
    xmin, xmax = min(xs), max(xs)
    wmax = max(o["week"] for o in pts) or 1
    chosen = {o["q"] for o in tl}

    def X(sup):      # few competitors on the right (where an RTL reader starts)
        v = (math.log10(sup + 10) - xmin) / ((xmax - xmin) or 1)
        return W - PR - v * (W - PL - PR)

    def Y(w):
        return H - PB - math.sqrt(w / wmax) * (H - PT - PB)

    xs_split, ys_split = X(500), Y(max(mid * 2, 10))
    xs_split = min(max(xs_split, PL), W - PR - 60)
    ys_split = min(max(ys_split, PT + 40), H - PB)
    g = [f"<rect x='{xs_split:.0f}' y='{PT}' width='{W - PR - xs_split:.0f}' height='{ys_split - PT:.0f}' "
         f"fill='#f3e7cc' opacity='.6' rx='8'/>",
         f"<text x='{xs_split + 10:.0f}' y='{ys_split - 10:.0f}' text-anchor='end' font-size='13' fill='#7a5714' "
         f"font-weight='700'>فرصت طلایی: تقاضای زیاد، رقیب کم</text>",
         f"<line x1='{PL}' y1='{H - PB}' x2='{W - PR}' y2='{H - PB}' stroke='#c9cdc5'/>",
         f"<text x='{W - PR}' y='{H - 16}' font-size='12' fill='#5b6476' text-anchor='start'>رقیب کم در باسلام</text>",
         f"<text x='{PL}' y='{H - 16}' font-size='12' fill='#5b6476' text-anchor='end'>رقیب زیاد</text>",
         f"<text x='{PL}' y='{PT - 10}' font-size='12' fill='#5b6476' text-anchor='end'>↑ فروش این هفته بیشتر</text>"]
    col = {"basalam": "#13877f", "etsy": "#b0822a", "google": "#1d2433"}
    # placed labels (x_right, x_left, y); the golden-area caption is one of them
    boxes = [(xs_split + 10 + 6.6 * 30, xs_split + 10, ys_split - 10)]

    def free(xr, xl, y):
        return xl > PL and all(not (abs(y - by) < 15 and xl < bxr and xr > bxl) for bxr, bxl, by in boxes)

    for o in sorted(pts, key=lambda o: (o["q"] in chosen, o["week"])):
        x, y = X(o["supply"]), Y(o["week"])
        c = col.get(o["source"], "#13877f")
        if o["q"] in chosen:
            g.append(f"<circle cx='{x:.1f}' cy='{y:.1f}' r='7' fill='{c}' stroke='#fff' stroke-width='2'>"
                     f"<title>{E(o['q'])}: {fa(o['week'])} فروش این هفته، {fa(o['supply'])} رقیب</title></circle>")
            wtxt = 6.6 * len(o["q"]) + 4
            for dy in (4, -12, 20, -28):
                if free(x - 10, x - 10 - wtxt, y + dy):
                    boxes.append((x - 10, x - 10 - wtxt, y + dy))
                    g.append(f"<text x='{x - 10:.1f}' y='{y + dy:.1f}' font-size='12' fill='#1d2433' "
                             f"text-anchor='start'>{E(o['q'])}</text>")
                    break
        else:
            g.append(f"<circle cx='{x:.1f}' cy='{y:.1f}' r='4' fill='{c}' opacity='.45'>"
                     f"<title>{E(o['q'])}: {fa(o['week'])} فروش این هفته، {fa(o['supply'])} رقیب</title></circle>")
    return (f"<div class='map'><svg viewBox='0 0 {W} {H}' role='img' aria-label='نقشه‌ی فرصت‌ها' direction='rtl' "
            f"font-family='Vazirmatn,Tahoma'>{''.join(g)}</svg></div>"
            "<div class='legend'><span><i class='dot d-turq'></i>از پرفروش‌های باسلام</span>"
            "<span><i class='dot d-gold'></i>از ترندهای اتسی</span><span><i class='dot d-ink'></i>از گوگل</span>"
            "<span>نقطه‌های بزرگ با نام: در لیست آزمایش</span></div>")


def _persona(m: dict) -> str:
    name, cls = MARKET[m["key"]]
    price = (f"{fa(m['price_median'], 0)} دلار" if m["key"] == "etsy" else f"{toman(m['price_median'])} تومان") \
        if m.get("price_median") else "—"
    fmt = lambda pairs: "، ".join(f"{E(k)} ({fa(v)}٪)" for k, v in pairs) or "—"  # noqa: E731
    return (f"<div class='persona {cls}'><h3>{name}</h3>"
            f"<p class='muted'>قیمت میانه‌ی {m['price_of']}</p><p class='big'>{price}</p>"
            f"<p><b>سبک:</b> {fmt(m['style'])}</p><p><b>جنس:</b> {fmt(m['material'])}</p>"
            f"<p><b>رنگ:</b> {fmt(m['color'])}</p><p><b>شخصی‌سازی‌شده:</b> {fa(m['personal'])}٪</p></div>")


def _cmp(rows, title, has_dk):
    head = "<th>اتسی</th><th>باسلام</th>" + ("<th>دیجی‌کالا</th>" if has_dk else "")
    out = [f"<div><h3>{title}</h3><table class='cmp'><tr><th></th>{head}</tr>"]
    for r in rows[:9]:
        cells = [("gold", r["etsy"]), ("turq", r["basalam"])] + ([("lapis", r.get("digikala", 0))] if has_dk else [])
        out.append(f"<tr><td>{E(r['name'])}</td>" + "".join(
            f"<td class='v'><span class='b b-{c}' style='width:{max(2, v * 1.3):.0f}px'></span>{fa(v)}٪</td>"
            for c, v in cells) + "</tr>")
    out.append("</table></div>")
    return "".join(out)


def _prices(rows, has_dk):
    def cell(s, usd=False):
        if not s:
            return "—"
        if usd:
            return f"{fa(s['low'])} – <b>{fa(s['median'])}</b> – {fa(s['high'])} دلار"
        return f"{toman(s['low'])} – <b>{toman(s['median'])}</b> – {toman(s['high'])}"
    head = "<th>اتسی</th><th>اتسی به تومان (میانه)</th><th>باسلام (تومان)</th>" + \
           ("<th>دیجی‌کالا (تومان)</th>" if has_dk else "")
    out = [f"<table><tr><th>نوع</th>{head}</tr>"]
    for r in rows:
        e = r["etsy"]
        out.append(f"<tr><td>{r['type']}</td><td>{cell(e, True)}</td>"
                   f"<td>{toman(e['median'] * C.USD_TOMAN) if e else '—'}</td><td>{cell(r['basalam'])}</td>"
                   + (f"<td>{cell(r.get('digikala'))}</td>" if has_dk else "") + "</tr>")
    out.append("</table><p class='muted'>هر خانه: ارزان (یک‌چهارم پایین) – <b>میانه</b> – گران (یک‌چهارم بالا). "
               f"دلار با نرخ {fa(C.USD_TOMAN)} تومان.</p>")
    return "".join(out)


def _trends(tr: list[dict]) -> str:
    rows = [r for r in tr if r.get("average") is not None]
    if not rows:
        return ""
    from .trends import MONTHS_FA
    out = ["<table><tr><th>کلمه</th><th>نسبت به پارسال<div class='muted'>(برای پیش‌بینی ضعیف)</div></th><th>ماه‌های اوج<div class='muted'>(قابل‌اعتمادتر)</div></th><th>اوج بعدی</th>"
           "<th>جست‌وجوهای در حال رشد</th></tr>"]
    for r in sorted(rows, key=lambda r: -(r.get("average") or 0)):
        y = r.get("yoy")
        yt = "—" if y is None else f"<span class='{'up' if y >= 10 else 'down' if y <= -10 else ''}'>" \
                                   f"{'+' if y > 0 else ''}{fa(round(y))}٪</span>"
        pm = "، ".join(MONTHS_FA.get(m, str(m)).split(" ")[1].strip("()") for m in r.get("peak_months") or []) or "—"
        if r.get("peak_months") and not r.get("seasonal"):
            pm += "<div class='muted'>فصلی بودنش ضعیف است</div>"
        nx = E(jalali(r.get("next_peak")) or "—")
        if r.get("order_by"):
            nx += f"<div class='muted'>سفارش تا {E(jalali(r['order_by']))}</div>"
        rq = r.get("breakout", [])[:3] + r.get("rising", [])[:4]
        rt = "".join(f"<span class='tag'>{E(q['query'])}</span>" for q in rq) or "—"
        kw = E(r["keyword"])
        link = f"<a href='{E(r['url'])}' target='_blank' rel='noopener'>{kw}</a>" if r.get("url") else kw
        out.append(f"<tr><td>{link}</td><td>{yt}</td><td>{pm}</td><td>{nx}</td><td>{rt}</td></tr>")
    return "".join(out) + "</table>"


def _opps(opps: list[dict]) -> str:
    out = ["<table><tr><th>جست‌وجو</th><th>فروش این هفته (۱۰ پرفروش باسلام)</th><th>رقیب در باسلام</th>"
           "<th>داغی تازه</th><th>بازه‌ی قیمت</th><th>همین طرح در دیجی‌کالا</th><th>برچسب</th></tr>"]
    for o in sorted(opps, key=lambda o: -o["score"])[:60]:
        link = "https://basalam.com/s?q=" + quote(o["q"])
        pr = f"{toman(o['price_low'])} – {toman(o['price_high'])}" if o.get("price_low") else "—"
        out.append(f"<tr><td><a href='{link}' target='_blank' rel='noopener'>{E(o['q'])}</a></td><td>{fa(o['week'])}</td>"
                   f"<td>{fa(o['supply'])}</td><td>{fa(round(o['momentum'] * 100))}٪</td><td>{pr}</td>"
                   f"<td>{fa(o['dk_match']) + ' از ۲۰' if 'dk_match' in o else '—'}</td><td>{_labs(o['labels'])}</td></tr>")
    return "".join(out) + ("</table><p class='muted'>«داغی تازه»: چند درصد از کل فروش ۱۰ پرفروش همین هفته بوده؛ "
                           "عدد بالا یعنی تازه داغ شده.</p>")


def _gallery(items, n=40):
    out = ["<div class='grid'>"]
    for p in items[:n]:
        if p["source"] == "etsy":
            sig = f"{fa(p['reviews'])} نظر برای فروشگاه" if p.get("reviews") else ""
            price = f"{fa(p['price_usd'], 2)} دلار" if p.get("price_usd") else ""
        elif p["source"] == "digikala":
            sig = f"رتبه‌ی {fa(p.get('position'))} پرفروش‌ها، {fa(p.get('reviews'))} امتیاز"
            price = f"{toman(p.get('price_toman'))} تومان"
        else:
            sig = f"{fa(p.get('sales_week') or 0)} فروش این هفته، {fa(p.get('sales_total'))} کل"
            price = f"{toman(p.get('price_toman'))} تومان"
        out.append(f"<div class='p'><a href='{E(p['url'])}' target='_blank' rel='noopener'>"
                   f"<img loading='lazy' src='{E(p.get('image') or '')}' alt=''>"
                   f"<b>{E(p.get('name_fa') or p['title'])}</b><div>{price}</div><div class='s'>{sig}</div>"
                   f"<div class='s'>{E(p.get('style', ''))}، {E(p.get('material', ''))}، {E(p.get('color', ''))}</div>"
                   f"</a></div>")
    return "".join(out) + "</div>"


def _timing(occ: list[dict], mt: dict) -> str:
    if not occ and not mt:
        return ""
    metal = "".join(f"<div><span class='muted'>{E(v['name'])}</span><b>{toman(v['toman'])} تومان</b></div>"
                    for v in mt.values())
    rows = []
    for o in occ:
        if o.get("quiet"):
            rows.append(f"<tr class='quiet'><td>{E(o['name'])}</td><td>{E(jalali(o['date']))} تا "
                        f"{E(jalali(o.get('until', '')))}</td><td>{fa(max(0, o['days_left']))} روز</td>"
                        f"<td colspan='2'>فروش جواهرِ جشن معمولاً کم است؛ سفارش زیاد نگیرید</td></tr>")
            continue
        ob = (f"<span class='{'soon' if o['days_left'] <= 35 else ''}'>{E(jalali(o['order_by']))}</span>"
              if o["order_by"] else "<span class='soon'>دیر است؛ فقط با موجودی فعلی</span>")
        ds = "، ".join(E(x) for x in o["designs"]) or f"<span class='muted'>{E('، '.join(o['themes']))}</span>"
        rows.append(f"<tr><td>{E(o['name'])}{' <span class=muted>(تاریخ قمری، حدودی)</span>' if o['approx'] else ''}</td>"
                    f"<td>{E(jalali(o['date']))}</td><td>{fa(o['days_left'])} روز</td><td>{ob}</td><td>{ds}</td></tr>")
    table = ("<table><tr><th>مناسبت</th><th>تاریخ</th><th>مانده</th><th>سفارش به سازنده تا</th>"
             "<th>طرح‌های مناسب از لیست آزمایش (یا موضوع‌های پرفروش)</th></tr>" + "".join(rows) + "</table>") if rows else ""
    return (f"<section id='timing'><h2>مناسبت‌ها و قیمت فلز</h2><p class='lead'>کی باید جنس آماده باشد، و قیمت امروز "
            f"نقره و طلا (منبع: tgju) برای سنجیدن سقف خرید قطعه‌های نقره.</p><div class='metal'>{metal}</div>{table}"
            f"</section>")


def _typed(sug: dict, opps: list[dict]) -> str:
    counts = (sug or {}).get("counts") or {}
    if not counts:
        return ""
    tested = {o["q"]: o for o in opps if o["source"] == "suggest"}
    chips = "".join(
        f"<span class='{'tested' if k in tested else ''}' title='{fa(v)} بار پیشنهاد شد'>{E(k)}"
        + (f" <b>{fa(tested[k]['week'])} فروش</b>" if k in tested else "") + "</span>"
        for k, v in list(counts.items())[:45])
    trend = "".join(f"<span>{E(k)}</span>" for k in (sug.get("trending") or [])[:15])
    return (f"<section id='typed'><h2>مردم چه تایپ می‌کنند</h2><p class='lead'>پیشنهادهای جعبه‌ی جست‌وجوی دیجی‌کالا "
            f"برای کلمه‌های جواهر؛ هرچه زودتر در فهرست، بیشتر پیشنهاد شده. آن‌هایی که رنگی‌اند طرح بودند و در باسلام هم "
            f"سنجیده شدند (فروش این هفته‌ی ۱۰ پرفروش).</p><div class='chips'>{chips}</div>"
            + (f"<h3 style='margin-top:18px'>پرجست‌وجوهای کل دیجی‌کالا در این لحظه</h3><div class='chips'>{trend}</div>"
               if trend else "") + "</section>")


def _makers(mk_: list[dict]) -> str:
    if not mk_:
        return ""
    from .makers import by_province
    prov = "".join(f"<span>{E(p)}: {fa(c)}</span>" for p, c in by_province(mk_))
    rows = "".join(
        f"<tr><td><a href='{E(m['url'])}' target='_blank' rel='noopener'>{E(m['name'])}</a></td>"
        f"<td>{E(m['city'])}{('، ' + E(m['province'])) if m['province'] else ''}</td>"
        f"<td>{'سازنده یا کارگاه' if m['maker'] else '<span class=muted>نامشخص یا فروشنده</span>'}</td>"
        f"<td>{fa(m['products'])}</td><td>{fa(m['sales'])}</td><td>{fa(m['week'])}</td>"
        f"<td>{E(m['since']).translate(FA_DIGITS) or '—'}</td></tr>" for m in mk_[:30])
    return (f"<section id='makers'><h2>سازنده‌های احتمالی</h2><p class='lead'>غرفه‌های باسلام که بین پرفروش‌های جواهر "
            f"بودند. «سازنده یا کارگاه» یعنی در معرفی غرفه نشانه‌ی ساخت (دست‌ساز، کارگاه، تولید، کسب‌وکار خانگی…) هست و "
            f"نشانه‌ی واردات نیست؛ قبل از همکاری، تماس و نمونه بگیرید.</p>"
            + (f"<div class='prov'>{prov}</div>" if prov else "")
            + "<table><tr><th>غرفه</th><th>شهر</th><th>نوع</th><th>محصول در پرفروش‌ها</th><th>فروش کل این محصولات</th>"
              f"<th>فروش این هفته</th><th>از سال</th></tr>{rows}</table></section>")


def render(name: str, when: str, st: dict, ex: dict, mk: list[dict], etsy: list[dict], bas: list[dict],
           dk: list[dict], opps: list[dict], tl: list[dict], tr: list[dict], cost: dict, mid: float,
           extra: dict | None = None) -> str:
    extra = extra or {}
    timing = _timing(extra.get("occasions") or [], extra.get("metals") or {})
    typed = _typed(extra.get("suggest") or {}, opps)
    makers_html = _makers(extra.get("makers") or [])
    has_dk = bool(dk)
    top = tl[0] if tl else None
    pick = ""
    if top:
        img = (top.get("images") or [{}])[0].get("src", "")
        pick = (f"<div class='pick'><img src='{E(img)}' alt=''><div><div class='k'>انتخاب اول این هفته</div>"
                f"<h3>{E(top.get('name') or top['q'])}</h3><div class='n'>{fa(top['week'])} فروش این هفته در باسلام، "
                f"{fa(top['supply'])} رقیب؛ قیمت فروش حدود {toman((top.get('eco') or {}).get('retail'))} تومان</div>"
                f"</div></div>")
    headline = ex.get("headline") or "گزارش ترند جواهرات دست‌ساز"
    sub = (f"پرفروش‌های {fa(st['n_etsy'])} محصول اتسی، {fa(st['n_basalam'])} باسلام"
           + (f" و {fa(st.get('n_digikala', 0))} دیجی‌کالا" if has_dk else "")
           + f" کنار هم؛ {fa(len(opps))} جست‌وجوی فرصت و {fa(len(tl))} طرح پیشنهادی برای آزمایش.")
    findings = "".join(f"<div class='finding'><b>{P(f['title'])}</b><span>{P(f['text'])}</span></div>"
                       for f in ex.get("findings", [])) or "<p class='muted'>تحلیل هوش مصنوعی این بار ساخته نشد.</p>"
    actions = "".join(f"<li>{P(a)}</li>" for a in ex.get("actions", []))
    risks = "".join(f"<li>{P(a)}</li>" for a in ex.get("risks", []))
    brief = (f"<div class='brief'><b>متنی برای تولیدکننده</b>{P(ex['maker_brief'])}</div>"
             if ex.get("maker_brief") else "")
    designs = "".join(_design(i, o) for i, o in enumerate(tl, 1)) or \
        "<p class='muted'>این هفته طرحی با شرایط آزمایش پیدا نشد.</p>"
    steps = "، ".join(f"{E(k)}: {fa(v['usd'], 3)} دلار" for k, v in cost.get("steps", {}).items())
    tr_html = _trends(tr)
    nav = [("خلاصه", "summary"), ("لیست آزمایش", "test")] + ([("مناسبت‌ها", "timing")] if timing else []) + \
          [("نقشه‌ی فرصت‌ها", "map"), ("سه بازار", "markets")] + ([("جست‌وجوی مردم", "typed")] if typed else []) + \
          ([("گوگل", "trends")] if tr_html else []) + ([("سازنده‌ها", "makers")] if makers_html else []) + \
          [("جزئیات", "details")]
    galleries = [("اتسی", etsy), ("باسلام", bas)] + ([("دیجی‌کالا", dk)] if has_dk else [])
    return f"""<!DOCTYPE html><html lang="fa" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>دست‌ساز — گزارش ترند {E(name)}</title>
<style>{CSS}</style></head><body>
<nav class="bar-top"><div class="wrap"><span class="brand">دست‌ساز</span>
{''.join(f'<a href="#{a}">{t}</a>' for t, a in nav)}</div></nav>
<header class="hero"><div class="wrap"><div><div class="date">گزارش ترند جواهرات · {E(when)}</div>
<h1>{P(headline)}</h1><p>{sub}</p>
<div class="markets"><span><b>{fa(len(tl))}</b>طرح برای آزمایش</span>
<span><b>{fa(sum(1 for o in opps if 'تقاضای زیاد، رقیب کم' in o['labels']))}</b>فرصت طلایی</span>
<span><b>{fa(cost.get('usd', 0), 2)}</b>دلار هزینه‌ی گزارش</span></div></div>{pick}</div></header>
<main class="wrap">
<section id="summary"><h2>خلاصه‌ی مدیریتی</h2>
<p class="lead">نتیجه‌گیری هوش مصنوعی فقط از عددهای همین گزارش؛ عددها را در بخش‌های پایین می‌توانید چک کنید.
این گزارش «ایده‌یاب» است، نه پیش‌گوی فروش: آزمون روی گذشته نشان داد فروش یک طرح خاص را از بیرون نمی‌شود دقیق پیش‌بینی کرد
(<a href="/backtest">دقت سیستم</a>)؛ داور، آزمایش کم و ارزان در <a href="/lab">آزمایشگاه</a> است.</p>
<div class="exec"><div>{findings}</div><div><div class="todo"><h3>کارهای این هفته</h3><ol>{actions}</ol></div>
{f'<div class="todo risk"><h3>ریسک‌ها و محدودیت داده</h3><ul>{risks}</ul></div>' if risks else ''}</div></div>{brief}</section>
<section id="test"><h2>لیست آزمایش این هفته</h2>
<p class="lead">از هر طرح فقط چند عدد بسازید، یک تا دو هفته فروش را بسنجید و فقط برنده‌ها را دوباره سفارش دهید.
عکس‌ها مرجع ترندند؛ سازنده نسخه‌ی خودش را بسازد. «خرید از سازنده» حداکثر {fa(round(C.BUY_SHARE * 100))}٪ قیمت فروش است
تا کارمزد، ارسال، تبلیغ و سود جا داشته باشد.</p>{designs}</section>
{timing}
<section id="map"><h2>نقشه‌ی فرصت‌ها</h2>
<p class="lead">هر نقطه یک جست‌وجو در باسلام است: بالاتر یعنی فروش این هفته بیشتر، راست‌تر یعنی رقیب کمتر.
بهترین جا گوشه‌ی بالا و راست است.</p>{_map(opps, tl, mid)}</section>
<section id="markets"><h2>سه بازار، سه مشتری</h2>
<p class="lead">پرفروش‌های هر بازار چه سبک و جنس و رنگی دارند و حدوداً چند می‌فروشند.</p>
<div class="three">{''.join(_persona(m) for m in mk)}</div>
<div class="cols">{_cmp(st['style'], 'سبک', has_dk)}{_cmp(st['material'], 'جنس', has_dk)}</div>
<div class="cols">{_cmp(st['color'], 'رنگ', has_dk)}<div><h3>قیمت هر نوع</h3>{_prices(st['prices'], has_dk)}</div></div>
</section>
{f'<section id="trends"><h2>گوگل ترندز ایران</h2><p class="lead">جست‌وجوی هر کلمه در گوگل ایران در ۵ سال اخیر: '
  f'چقدر نسبت به پارسال تغییر کرده، کدام ماه‌ها اوج دارد و کی باید جنس آماده باشد. جست‌وجوهای در حال رشدِ مربوط به '
  f'جواهر در باسلام و دیجی‌کالا هم بررسی شدند. آزمون روی ۵ سال گذشته نشان داد <b>ماه‌های اوج فصلی</b> قابل‌اعتمادند '
  f'ولی «رشد اخیر» به‌تنهایی آینده را پیش‌بینی نمی‌کند (<a href="/backtest">دقت سیستم</a>).</p>{tr_html}</section>' if tr_html else ''}
{typed}
{makers_html}
<section id="details"><h2>جزئیات</h2>
<details><summary>همه‌ی جست‌وجوهای فرصت ({fa(len(opps))})</summary><div class="in">{_opps(opps)}</div></details>
{''.join(f'<details><summary>۴۰ پرفروش اول {t}</summary><div class="in">{_gallery(items)}</div></details>'
         for t, items in galleries)}
</section></main>
<footer class="wrap">پرفروش اتسی بر اساس ترتیب خود اتسی و تعداد نظرهای فروشگاه؛ باسلام بر اساس فروش این هفته و فروش کل؛
دیجی‌کالا (که تعداد فروش نشان نمی‌دهد) بر اساس ترتیب «پرفروش‌ترین» و تعداد امتیازدهنده‌ها. سبک، جنس و رنگ را
هوش مصنوعی از روی عکس و عنوان تشخیص داده و ممکن است چند مورد اشتباه باشد. «نوع» (گردنبند، گوشواره…) مقایسه نشده
چون برای هر نوع به یک اندازه جست‌وجو شده است.<br>هزینه به تفکیک: {steps or '—'}</footer>
</body></html>"""


def _pct(x, sign=False) -> str:
    if x is None:
        return "—"
    v = round(x * 100)
    return ("+" if sign and v > 0 else "") + fa(v) + "٪"


def _jm(ym: str) -> str:
    return jalali(ym + "-15").split(" ", 1)[1] if ym else ""


def backtest_page(res: list[dict]) -> str:
    src = {"trends": ("گوگل ترندز ایران", "میزان جست‌وجوی هر کلمه در گوگل، ماه به ماه"),
           "reviews": ("نظرهای خریداران باسلام", "تعداد نظرهای ثبت‌شده هر ماه برای پرفروش‌های هر طرح؛ تقریبی از فروش"),
           "reviews_dk": ("نظرهای خریداران دیجی‌کالا", "تعداد نظرهای ثبت‌شده هر ماه برای پرفروش‌های هر طرح؛ تقریبی از فروش"),
           "reviews_attr": ("باسلام، در سطح موتیف", "همه‌ی طرح‌های یک موتیف (مثل «پاپیون» یا «اسم») با هم؛ آیا موتیف از تک‌طرح قابل‌پیش‌بینی‌تر است؟"),
           "reviews_attr_dk": ("دیجی‌کالا، در سطح موتیف", "همه‌ی طرح‌های یک موتیف با هم")}
    blocks = []
    for r in res:
        sc = r.get("scores") or {}
        base = sc.get("_base") or {}
        ms = [(k, v) for k, v in sc.items() if not k.startswith("_")]
        best = max((v for k, v in ms if k != "persist"), key=lambda v: v["direction"], default=None)
        rows = "".join(
            f"<tr{' class=hl' if k == 'ours' else ''}><td>{E(v['name'])}</td><td><b>{_pct(v['direction'])}</b></td>"
            f"<td>{fa(round(v['error'] * 100))} درصد</td><td>{_pct(v['pick_hit'])}</td>"
            f"<td>{_pct(v['pick_growth'], True)}</td></tr>" for k, v in ms)
        ex = r.get("example") or []
        exr = ""
        if len(ex) > 1:
            head = ex[0]
            exr = (f"<h3>یک نمونه‌ی واقعی: پیش‌بینی در {E(_jm(head['cutoff']))} برای سه ماه بعد</h3>"
                   "<table><tr><th>کلمه / طرح</th><th>روش گزارش گفت</th><th>پارسال همین موقع</th><th>روند اخیر</th>"
                   "<th>واقعاً شد</th></tr>" + "".join(
                       f"<tr><td>{E(x['name'])}</td><td>{_pct(x['ours'], True)}</td><td>{_pct(x['seasonal'], True)}</td>"
                       f"<td>{_pct(x['momentum'], True)}</td><td><b>{_pct(x['actual'], True)}</b></td></tr>"
                       for x in ex[1:16]) + "</table>")
        name, what = src.get(r["source"], (r["source"], ""))
        name += " — " + {"jewelry": "جواهر", "kitchen": "لوازم آشپزخانه (دسته‌ی کنترل)",
                         "categories": "در سطح دسته (رادار)"}.get(r.get("cat", "jewelry"), "")
        verdict = ""
        if "ours" in sc and "persist" in sc:
            o, p_ = sc["ours"], sc["persist"]
            gain = o["direction"] - p_["direction"]
            verdict = (f"<div class='verdict {'good' if gain > 0.05 else 'bad'}'>"
                       f"روش گزارش در {_pct(o['direction'])} موارد جهت (بالا، پایین یا ثابت) را درست گفت؛ "
                       f"حدس «هیچ تغییری نمی‌کند» {_pct(p_['direction'])}. "
                       + ("یعنی روش ما واقعاً چیزی بیشتر از حدس ساده می‌فهمد." if gain > 0.05 else
                          "یعنی روش ما فعلاً از حدس ساده بهتر نیست و باید اصلاح شود.")
                       + (f" ۵ انتخاب اول روش گزارش در {_pct(o['pick_hit'])} موارد واقعاً رشد کردند؛ "
                          f"به‌طور تصادفی {_pct(base.get('up'))} رشد می‌کردند." if o.get("pick_hit") is not None else "")
                       + "</div>")
        blocks.append(
            f"<section><h2>{E(name)}</h2><p class='lead'>{E(what)}. بازه‌ی داده: {E(_jm(r['months'][0]) if r.get('months') else '')}"
            f" تا {E(_jm(r['months'][1]) if r.get('months') else '')}؛ {fa(r.get('keywords', 0))} مورد، "
            f"{fa(base.get('cases', 0))} آزمون (هر مورد در هر ماه یک آزمون). هزینه {fa(r.get('usd', 0), 3)} دلار.</p>"
            f"{verdict}<table><tr><th>روش</th><th>جهت درست</th><th>خطای متوسط</th><th>۵ انتخاب اول که رشد کردند</th>"
            f"<th>رشد متوسط ۵ انتخاب اول</th></tr>{rows}"
            f"<tr class='muted'><td>انتخاب تصادفی</td><td>—</td><td>—</td><td>{_pct(base.get('up'))}</td>"
            f"<td>{_pct(base.get('growth'), True)}</td></tr></table>{exr}</section>")
    body = "".join(blocks) or "<p>هنوز آزمونی اجرا نشده.</p>"
    return f"""<!DOCTYPE html><html lang="fa" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>دست‌ساز — دقت سیستم</title>
<style>{CSS}
.verdict{{padding:12px 16px;border-radius:10px;margin:0 0 16px;font-weight:600}}.verdict.good{{background:#e3f4ef}}
.verdict.bad{{background:#fbe9ec}}tr.hl td{{background:#fff7e6}}</style></head><body>
<nav class="bar-top"><div class="wrap"><span class="brand">دست‌ساز</span><a href="/">خانه</a></div></nav>
<header class="hero"><div class="wrap"><div><div class="date">آزمون روی گذشته</div><h1>سیستم پیش‌بینی چقدر درست می‌گوید؟</h1>
<p>به چند ماه در گذشته برمی‌گردیم، هر روش فقط با داده‌ی تا آن روز سه ماه بعد را پیش‌بینی می‌کند، و بعد با
اتفاقی که واقعاً افتاد مقایسه می‌کنیم. این کار برای هر ماه تکرار می‌شود تا شانس اثرش را از دست بدهد.</p></div></div></header>
<main class="wrap">{body}
<section><h2>این عددها یعنی چه</h2><ul>
<li><b>جهت درست:</b> در چند درصد آزمون‌ها گفت «بالا می‌رود / پایین می‌آید / ثابت می‌ماند» و درست بود. تغییر کمتر از ۱۰٪ «ثابت» حساب شده.</li>
<li><b>خطای متوسط:</b> پیش‌بینی چند درصد با واقعیت فاصله داشت. کمتر بهتر.</li>
<li><b>۵ انتخاب اول:</b> اگر هر ماه فقط ۵ موردی را که روش بیشترین رشد برایشان گفته انتخاب می‌کردیم، چند درصدشان واقعاً رشد کردند. ردیف «انتخاب تصادفی» مبنای مقایسه است.</li>
<li>تعداد نظرها تقریبی از فروش است و نمونه‌ها کم؛ عددها را نشانه بدانید، نه حکم قطعی.</li></ul></section>
</main></body></html>"""


def _shell(title: str, kicker: str, lead: str, body: str, extra_css: str = "") -> str:
    return f"""<!DOCTYPE html><html lang="fa" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>دست‌ساز — {E(title)}</title>
<style>{CSS}
.verdict{{padding:12px 16px;border-radius:10px;margin:0 0 16px;font-weight:600}}.verdict.good{{background:#e3f4ef}}
.verdict.bad{{background:#fbe9ec}}tr.hl td{{background:#fff7e6}}
form.inline{{display:flex;gap:6px;flex-wrap:wrap;align-items:center}}form.inline input,form.inline select{{font:inherit;
padding:4px 6px;border:1px solid var(--line);border-radius:6px;max-width:170px}}form.inline input.w{{max-width:240px}}
label.num{{display:flex;flex-direction:column;font-size:12px;color:var(--soft)}}label.num input{{max-width:80px}}
.btn{{font:inherit;background:var(--lapis,#2f4b85);color:#fff;border:0;border-radius:8px;padding:6px 14px;cursor:pointer}}
.v-win{{color:#13877f;font-weight:700}}.v-drop{{color:#a43f55;font-weight:700}}.v-early{{color:#8a8f99}}
.bar{{height:8px;background:#e8eaee;border-radius:4px;min-width:80px}}.bar i{{display:block;height:8px;border-radius:4px;background:#13877f}}
{extra_css}</style></head><body>
<nav class="bar-top"><div class="wrap"><span class="brand">دست‌ساز</span><a href="/">خانه</a><a href="/lab">آزمایشگاه</a>
<a href="/voice">صدای مشتری</a><a href="/needs">نیازهای کادو</a><a href="/radar">رادار دسته‌ها</a><a href="/telegram">تلگرام</a><a href="/ads">ادز</a>
<a href="/backtest">دقت سیستم</a></div></nav>
<header class="hero"><div class="wrap"><div><div class="date">{E(kicker)}</div><h1>{E(title)}</h1><p>{lead}</p></div></div></header>
<main class="wrap">{body}</main></body></html>"""


def _opts(d: dict, sel: str = "") -> str:
    return "".join(f"<option value='{E(k)}'{' selected' if k == sel else ''}>{E(v)}</option>" for k, v in d.items())


def lab_page(b: dict, changes: list[dict] | None = None, snaps: int = 0, ideas: str = "") -> str:
    from . import lab as L
    rows = []
    for t in sorted(b["rows"], key=lambda r: (bool(r["closed"]), r["channel"], -(r["rate"] or 0))):
        n = t["now"]
        share = t.get("share")
        form = "" if t["closed"] else (
            f"<form class='inline' method='post' action='/lab/update/{E(t['id'])}'>"
            + "".join(f"<label class='num'>{lab_fa}<input name='{k}' type='number' min='0' value='{n.get(k, 0)}'></label>"
                      for k, lab_fa in (("views", "بازدید"), ("saves", "ذخیره"), ("messages", "پیام"),
                                        ("carts", "سبد"), ("orders", "سفارش"), ("noes", "رد/رد شدن"), ("cost", "هزینه (تومان)")))
            + "<select name='close'><option value=''>باز</option><option value='win'>برنده، ببند</option>"
              "<option value='drop'>کنار بگذار</option><option value='stop'>متوقف</option></select>"
              "<button class='btn'>ثبت</button></form>")
        rows.append(
            f"<tr{' class=hl' if t['control'] else ''}><td><b>{E(t['name'])}</b><div class='muted'>"
            f"{E(L.CHANNELS.get(t['channel'], ''))} · {E(L.STAGES.get(t['stage'], ''))} · منبع: {E(L.SOURCES.get(t['source'], ''))}"
            f"{' · ' + toman(t['price']) + ' تومان' if t.get('price') else ''} · از {E(jalali(t['started']))}"
            f"{''.join(' <span class=tag>' + E(x) + '</span>' for x in t.get('tags') or [])}</div></td>"
            f"<td>{fa(n.get('views', 0))}</td><td>{_pct(t['rate']) if t['rate'] is not None else '—'}"
            f"{'<div class=muted>رد: ' + _pct(t['no_rate']) + '</div>' if t.get('no_rate') else ''}</td>"
            f"<td class='v-{t['verdict']}'>{E(t['verdict_fa'])}</td>"
            f"<td>{'' if share is None else f'<div class=bar><i style=width:{round(100 * share)}%></i></div>{_pct(share)}'}</td>"
            f"<td>{form}</td></tr>")
    ctrl = "، ".join(f"{E(L.CHANNELS[c])}: {_pct(r)}" for c, r in b["control"].items() if r is not None) or \
        "هنوز طرح کنترلی ثبت نشده؛ در هر کانال یک طرح با فروش متوسط را «کنترل» بگذارید"
    src = "".join(f"<tr><td>{E(L.SOURCES.get(k, k))}</td><td>{fa(v['tests'])}</td><td>{fa(v['wins'])}</td>"
                  f"<td>{_pct(v['wins'] / v['tests']) if v['tests'] else '—'}</td></tr>"
                  for k, v in sorted(b["sources"].items(), key=lambda kv: -kv[1]["tests"]))
    tags = "".join(f"<tr><td>{E(k)}</td><td>{fa(v['tests'])}</td><td>{fa(v['wins'])}</td><td>{fa(v['drops'])}</td>"
                   f"<td>{_pct(v['wins'] / v['tests'])}</td></tr>"
                   for k, v in sorted(b.get("tags", {}).items(), key=lambda kv: -kv[1]["tests"]))
    chs = "".join(f"<tr><td>{E(L.CHANNELS.get(k, k))}</td><td>{fa(v['tests'])}</td><td>{fa(v['wins'])}</td>"
                  f"<td>{_pct(v['rate']) if v['rate'] is not None else '—'}</td>"
                  f"<td>{toman(v['cost_per']) + ' تومان' if v.get('cost_per') else '—'}</td></tr>"
                  for k, v in sorted(b.get("channels", {}).items(), key=lambda kv: -kv[1]["tests"]))
    multi = "".join(f"<tr><td>{E(name)}</td><td>" + "، ".join(
        f"{E(L.CHANNELS.get(x['channel'], x['channel']))}: {_pct(x['rate']) if x['rate'] is not None else '—'}"
        for x in sorted(v, key=lambda x: -(x['rate'] or 0))) + "</td></tr>" for name, v in b.get("multi", {}).items())
    dist = (f"<section><h2>توزیع: کدام کانال</h2><p class='lead'>ایده‌ی خوب در کانال اشتباه، نتیجه‌ی بد می‌دهد. "
            f"یک طرح را هم‌زمان در ۲ تا ۳ کانال بگذارید (برای هر کانال یک آزمایش با همان اسم) تا معلوم شود مشکل از طرح است یا کانال. "
            f"«هزینه برای هر علاقه‌مند» معیار مقایسه‌ی کانال‌های پولی است.</p>"
            f"<table><tr><th>کانال</th><th>آزمایش</th><th>برنده</th><th>نرخ علاقه</th><th>هزینه برای هر علاقه‌مند</th></tr>"
            f"{chs or '<tr><td colspan=5 class=muted>—</td></tr>'}</table>"
            + (f"<h3>یک طرح، چند کانال</h3><table><tr><th>طرح</th><th>نرخ علاقه در هر کانال</th></tr>{multi}</table>" if multi else "")
            + "</section>")
    ch = ""
    if changes:
        ch = ("<section><h2>تغییر فروش نسبت به هفته‌ی پیش (باسلام)</h2><table><tr><th>جست‌وجو</th><th>هفته‌ی پیش</th>"
              "<th>این هفته</th><th>تغییر</th><th>تغییر تعداد رقیب</th><th>مرحله</th></tr>" + "".join(
                  f"<tr><td>{E(c['q'])}</td><td>{fa(c['prev'])}</td><td>{fa(c['now'])}</td>"
                  f"<td>{_pct(c['change'], True)}</td><td>{fa(c['supply_change'])}</td><td>{E(c.get('stage', ''))}</td></tr>"
                  for c in changes[:30])
              + "</table></section>")
    body = f"""<section><h2>آزمایش‌ها</h2>
<p class='lead'>اعداد را «کل تا امروز» وارد کنید (نه فقط امروز). علاقه = پیام + سبد خرید + سفارش (+ ذخیره با وزن کم).
«رد» یعنی سیگنال منفی: رأی «نه» در نظرسنجی استوری، یا رد شدن سریع از استوری. هر پست یا استوری فقط یک طرح، تا معلوم باشد واکنش مال کدام است.
نرخ کنترل الان: {ctrl}. ستون «سهم نمایش» می‌گوید در پست‌ها و ویترین بعدی چقدر جا به هر طرح بدهید.</p>
<table><tr><th>طرح</th><th>بازدید</th><th>نرخ علاقه</th><th>تصمیم</th><th>سهم نمایش</th><th>ثبت عددهای امروز</th></tr>
{''.join(rows) or '<tr><td colspan=6 class=muted>هنوز آزمایشی نیست.</td></tr>'}</table></section>
<section><h2>آزمایش تازه</h2><form class='inline' method='post' action='/lab/add'>
<input class='w' name='name' placeholder='اسم طرح' required><input class='w' name='query' placeholder='عبارت جست‌وجو در باسلام (اختیاری)'>
<select name='channel'>{_opts(L.CHANNELS)}</select><select name='stage'>{_opts(L.STAGES)}</select>
<select name='source'>{_opts(L.SOURCES)}</select><input name='price' type='number' placeholder='قیمت (تومان)'>
<label><input type='checkbox' name='control' value='1'> طرح کنترل</label>
<input class='w' name='tags' placeholder='ویژگی‌ها با ویرگول: پاپیون، طلایی، زیر ۳۰۰، کادو، اسم‌دار'>
<input class='w' name='note' placeholder='یادداشت'>
<button class='btn'>اضافه کن</button></form></section>
{ideas}
{dist}
<section><h2>کدام منبع ایده برنده می‌سازد</h2><p class='lead'>با هر آزمایش این جدول دقیق‌تر می‌شود؛ همین «حافظه»ی ماشین است.</p>
<table><tr><th>منبع</th><th>آزمایش</th><th>برنده</th><th>درصد برد</th></tr>{src or '<tr><td colspan=4 class=muted>—</td></tr>'}</table></section>
{ch}
<section><h2>کدام ویژگی برنده می‌شود</h2><p class='lead'>مثل تیک‌تاک: به‌جای «این طرح»، یاد می‌گیریم «این موتیف، رنگ، قیمت یا کاربرد».
فقط آزمایش‌های تمام‌شده (برنده یا کنار) حساب می‌شوند.</p>
<table><tr><th>ویژگی</th><th>آزمایش تمام‌شده</th><th>برنده</th><th>کنار</th><th>درصد برد</th></tr>{tags or '<tr><td colspan=5 class=muted>—</td></tr>'}</table></section>
<section><h2>قانون تصمیم (قبل از آزمایش ثابت است)</h2><ul>
<li>{_pct(L.EXPLORE)} جای نمایش همیشه برای طرح‌های تازه (زیر {fa(L.MIN_VIEWS)} بازدید) است تا ترند تازه دیده شود.</li>
<li>زیر {fa(L.MIN_VIEWS)} بازدید: زود است.</li>
<li>برنده: نرخ علاقه حداقل {fa(L.WIN_X, 1)} برابر طرح کنترل همان کانال و حداقل {_pct(L.WIN_ABS)}.</li>
<li>کنار بگذار: بعد از {fa(2 * L.MIN_VIEWS)} بازدید، کمتر از نصف کنترل.</li>
<li>عکس هفتگی فروش باسلام: {fa(snaps)} بار گرفته شده.</li></ul></section>"""
    return _shell("آزمایشگاه", "ماشین آزمایش", "هر طرح کم و ارزان امتحان می‌شود، برنده‌ها بیشتر دیده و سفارش داده می‌شوند، "
                  "بازنده‌ها زود کنار می‌روند؛ و ماشین یاد می‌گیرد کدام منبع ایده درست می‌گوید.", body)


def voice_page(v: dict | None) -> str:
    if not v:
        return _shell("صدای مشتری", "نظر خریداران", "هنوز اجرا نشده؛ از صفحه‌ی اول «صدای مشتری» را بزنید.", "")
    kinds = {"complaint": ("شکایت", "down"), "praise": ("تعریف", "up"), "wish": ("خواسته‌ی برآورده‌نشده", "")}
    rows = "".join(
        f"<tr><td><b>{E(t['theme'])}</b><div class='muted'>{'، '.join('«' + E(x) + '»' for x in t.get('examples', [])[:2])}</div></td>"
        f"<td><span class='{kinds.get(t.get('kind'), ('', ''))[1]}'>{E(kinds.get(t.get('kind'), (t.get('kind', ''), ''))[0])}</span></td>"
        f"<td>{fa(t['count'])}<div class='muted'>{_pct(t.get('share'))}</div></td><td>{E(t.get('fix', ''))}</td></tr>"
        for t in v["themes"])
    ig = "".join(
        f"<tr><td>{E(p['page'])}</td><td>{E(p['caption'])}</td><td>{fa(p['intent'])} از {fa(p['comments'])}</td>"
        f"<td>{fa(p['likes'])}</td><td><a href='{E(p['url'])}' target='_blank' rel='noopener'>پست</a></td></tr>"
        for p in v.get("instagram", [])[:20])
    st = " · ".join(f"{fa(k)} ستاره: {fa(n)}" for k, n in v.get("stars", {}).items())
    body = (f"<section><h2>موضوع‌های نظر خریداران</h2><p class='lead'>{fa(v['reviews'])} نظر از پرفروش‌های "
            f"{fa(len(v['designs']))} طرح در باسلام و دیجی‌کالا ({st}). هر شکایت بزرگ یک «نسخه‌ی بهتر» است.</p>"
            f"<table><tr><th>موضوع</th><th>نوع</th><th>تعداد</th><th>برای نسخه‌ی ما</th></tr>{rows}</table></section>"
            + (f"<section><h2>پست‌هایی که قصد خرید آوردند (اینستاگرام)</h2><p class='lead'>کامنت‌هایی مثل «قیمت؟»، "
               f"«موجوده؟»، «برای کادو» از لایک ارزشمندترند.</p><table><tr><th>پیج</th><th>متن پست</th>"
               f"<th>کامنت قصد خرید</th><th>لایک</th><th></th></tr>{ig}</table></section>" if ig else ""))
    return _shell("صدای مشتری", f"نظر خریداران · {jalali(v['date'])}", "مشتری‌ها از چه شاکی‌اند، چه چیزی را دوست دارند و "
                  "چه می‌خواهند که پیدا نمی‌کنند.", body)


def needs_page(n: dict | None) -> str:
    if not n:
        return _shell("نیازهای کادو", "نیاز", "هنوز اجرا نشده؛ از صفحه‌ی اول «نیازهای کادو» را بزنید.", "")
    t = n["table"]
    cells = "".join(f"<tr><td>{E(c['for'])}</td><td>{E(c['occasion'])}</td><td>{fa(c['n'])}</td></tr>" for c in t["cells"][:25])
    ideas = "".join(f"<tr><td>{E(i.get('need', ''))}</td><td><b>{E(i.get('design', ''))}</b></td><td>{E(i.get('search', ''))}</td>"
                    f"<td>{P(i.get('why', ''))}</td></tr>" for i in n.get("ideas", []))
    said = "".join(f"<span>{E(k)} <b>{fa(v)}</b></span>" for k, v in t["ideas"][:30])
    b = t.get("budgets") or []
    bud = f"میانه‌ی بودجه‌ی گفته‌شده: {toman(b[len(b) // 2] * 1000)} تومان ({fa(len(b))} مورد)" if b else ""
    src = "، ".join(f"{E(k)}: {fa(v)}" for k, v in n.get("sources", {}).items())
    body = (f"<section><h2>ایده‌های آزمایش از روی نیازها</h2><table><tr><th>نیاز</th><th>طرح پیشنهادی</th>"
            f"<th>جست‌وجو در باسلام</th><th>چرا</th></tr>{ideas}</table></section>"
            f"<section><h2>برای چه کسی، چه مناسبتی</h2><p class='lead'>{fa(n['phrases'])} عبارت ({src}). "
            f"{_pct(t['jewelry_share'])} به جواهر و اکسسوری مربوط بود. {bud}</p>"
            f"<table><tr><th>برای</th><th>مناسبت</th><th>تعداد</th></tr>{cells}</table></section>"
            f"<section><h2>محصول‌هایی که خود مردم گفتند</h2><div class='chips'>{said}</div></section>")
    return _shell("نیازهای کادو", f"دم بلند · {jalali(n['date'])}", "مردم وقتی نمی‌دانند چه بخرند چه می‌پرسند؛ "
                  "هر نیاز پرتکرار یک ایده‌ی آزمایش است.", body,
                  ".chips{display:flex;flex-wrap:wrap;gap:6px}.chips span{background:#fff;border:1px solid var(--line);"
                  "border-radius:999px;padding:2px 12px}")


def ideas_box(needs_ideas: list[dict], themes: list[dict], tg: list[dict]) -> str:
    """Ready-made test ideas with a one-click «add to lab» (source kept, so the lab learns which source wins)."""
    def add(name, query, source, note=""):
        return (f"<form class='inline' method='post' action='/lab/add'><input type='hidden' name='name' value='{E(name)}'>"
                f"<input type='hidden' name='query' value='{E(query)}'><input type='hidden' name='source' value='{source}'>"
                f"<input type='hidden' name='note' value='{E(note)}'><input type='hidden' name='channel' value='instagram'>"
                f"<button class='btn'>به آزمایشگاه</button></form>")
    rows = [f"<tr><td>{E(i.get('design', ''))}<div class='muted'>{E(i.get('need', ''))}"
            f"{'<br>کانال پیشنهادی: ' + E('، '.join(i.get('channels') or [])) if i.get('channels') else ''}</div></td><td>نیاز کادو</td>"
            f"<td>{add(i.get('design', ''), i.get('search', ''), 'needs', i.get('need', ''))}</td></tr>" for i in needs_ideas[:12]]
    rows += [f"<tr><td>نسخه‌ی بهتر: {E(t.get('fix', ''))}<div class='muted'>{E(t['theme'])} ({fa(t['count'])} نظر)</div></td>"
             f"<td>نظر خریداران</td><td>{add('نسخه‌ی بهتر — ' + t['theme'], '', 'voice', t.get('fix', ''))}</td></tr>"
             for t in themes if t.get("kind") in ("complaint", "wish") and t.get("fix")][:8]
    rows += [f"<tr><td>{E(t['q'])}<div class='muted'>{fa(t['posts'])} پست در {E('، '.join(t['channels'][:3]))}</div></td>"
             f"<td>تلگرام (۳۰ روز اخیر)</td><td>{add(t['q'], t['q'], 'telegram')}</td></tr>" for t in tg[:8]]
    if not rows:
        return ""
    return ("<section><h2>ایده‌های آماده برای آزمایش</h2><p class='lead'>از «نیازهای کادو»، «صدای مشتری» و تلگرام. "
            "با یک کلیک به آزمایشگاه می‌روند و منبعشان ثبت می‌شود.</p><table><tr><th>ایده</th><th>منبع</th><th></th></tr>"
            + "".join(rows) + "</table></section>")


def ads_page(date: str, rows: list[dict]) -> str:
    tr = "".join(f"<tr><td>{E(r['keyword'])}</td><td>{fa(r['avg'])}</td><td>{_pct((r['three_month'] or 0) / 100, True) if r['three_month'] is not None else '—'}</td>"
                 f"<td>{_pct((r['yoy'] or 0) / 100, True) if r['yoy'] is not None else '—'}</td><td>{E(r['competition'])}</td></tr>"
                 for r in sorted(rows, key=lambda r: -(r['avg'] or 0)))
    body = (f"<section><h2>بارگذاری خروجی ماهانه</h2><p class='lead'>در Keyword Planner گوگل ادز، کلمه‌ها را بزنید، مکان را "
            f"«همه‌ی کشورها» بگذارید و دکمه‌ی دانلود (فایل csv) را بزنید؛ همان فایل را اینجا بدهید.</p>"
            f"<form method='post' action='/ads/upload' enctype='multipart/form-data'><input type='file' name='file' accept='.csv' required> "
            f"<button class='btn'>بارگذاری</button></form></section>"
            + (f"<section><h2>آخرین خروجی ({E(jalali(date))})</h2><table><tr><th>کلمه</th><th>جست‌وجوی ماهانه</th>"
               f"<th>۳ ماه اخیر</th><th>نسبت به پارسال</th><th>رقابت</th></tr>{tr}</table></section>" if rows else ""))
    return _shell("گوگل ادز", "جست‌وجو بیرون از ایران", "فارسی‌زبان‌های بیرون از ایران و بازارهای خارجی؛ نشانه‌ی کمکی، نه اصلی.", body)


def telegram_page(chs: list[str], counts: dict, recent: list[dict]) -> str:
    rows = "".join(f"<tr><td>{E(r['q'])}</td><td>{fa(r['posts'])}</td><td>{fa(round(r['score'], 1))}</td>"
                   f"<td>{E('، '.join(r['channels']))}</td></tr>" for r in recent[:30])
    cnt = "، ".join(f"{E(c)}: {fa(counts.get(c, 0))} پست" for c in chs) or "هنوز کانالی ثبت نشده"
    body = (f"<section><h2>کانال‌ها</h2><p class='lead'>{cnt}</p><form method='post' action='/telegram/channels'>"
            f"<textarea name='channels' rows='5' style='width:100%;font:inherit'>{E(chr(10).join(chs))}</textarea>"
            f"<p class='muted'>هر خط یک کانال عمومی (مثل @name یا t.me/name). فقط کانال‌های عمومی خوانده می‌شوند.</p>"
            f"<button class='btn'>ذخیره</button></form></section>"
            + (f"<section><h2>طرح‌هایی که کانال‌ها در ۳۰ روز اخیر جلو بردند</h2><p class='lead'>امتیاز = بازدید پست‌های آن طرح "
               f"نسبت به بازدید معمول همان کانال.</p><table><tr><th>طرح</th><th>پست</th><th>امتیاز</th><th>کانال‌ها</th></tr>"
               f"{rows}</table></section>" if rows else ""))
    return _shell("تلگرام", "کانال‌های جواهر", "کانال‌های عمومی تلگرام: چه طرحی را جلو می‌برند و چند ماه زودتر از فروش باسلام خبر می‌دهند.", body)


def radar_page(rows: list[dict], n_cats: int, weeks: int, trends: dict | None = None) -> str:
    seas = {}
    if trends:
        for x in (trends.get("example") or [])[1:]:
            seas[x["name"]] = x
    def src(r, key):
        v = r.get(key)
        return "—" if v is None else fa(v)

    tr = "".join(
        f"<tr><td><b>{E(r['q'])}</b><div class='muted'>{E(r['name'])} · {E(r['top'])}</div></td>"
        f"<td><b>{fa(round(r.get('score', 0) * 100))}</b></td>"
        f"<td>{E('، '.join(r.get('strong') or [])) or '—'}<div class='muted'>{fa(r.get('agree', 0))} از {fa(r.get('n_src', 0))} منبع</div></td>"
        f"<td>{fa(r['week'])}</td><td>{fa(r.get('supply'))}</td><td>{fa(round(r['gap'], 1))}</td>"
        f"<td>{src(r, 'dk_reviews')}</td><td>{src(r, 'g_suggest')}</td><td>{src(r, 'ads')}</td><td>{src(r, 'ig_posts')}<div class='muted'>{src(r, 'ig_day')} در روز</div></td>"
        f"<td>{_pct(r['change'], True) if r.get('change') is not None else '—'}</td><td>{E(r['stage'])}</td>"
        f"<td>{toman(r.get('price'))}</td>"
        f"<td>{_pct(seas[r['q']]['season_avg'], True) if r['q'] in seas and seas[r['q']].get('season_avg') is not None else '—'}</td></tr>"
        for r in rows[:150])
    body = (f"<section><h2>دسته‌ها به ترتیب نمره‌ی چندمنبعی</h2><p class='lead'>{fa(n_cats)} دسته از فهرست کامل Etsy، به فارسیِ جست‌وجوی "
            f"ایرانی‌ها. یک فروشگاه به‌تنهایی یک‌طرفه است (مشتری باسلام با مشتری دیجی‌کالا و اینستاگرام فرق دارد)، پس هر منبع "
            f"دسته‌ها را جدا رتبه می‌دهد و «نمره» میانگین رتبه‌ها از ۱۰۰ است. «قوی در» = منبع‌هایی که دسته در یک‌سوم بالای آن‌هاست؛ "
            f"دسته‌ای که در همه‌ی منبع‌ها قوی است مطمئن‌ترین است، و دسته‌ای که فقط در یک منبع قوی است کانال فروشش را نشان می‌دهد.</p>"
            f"<p class='muted'>باسلام = فروش این هفته‌ی محصولات مرتبط · دیجی‌کالا = نظرهای پرفروش‌های مرتبط (اندازه‌ی بازار عمومی) · "
            f"گوگل = چند پیشنهاد جست‌وجوی گوگل این عبارت را دارد (۰ تا ۱۰) · Ads = جست‌وجوی ماهانه از فایل Keyword Planner (اگر بارگذاری شده) · اینستاگرام = تعداد پست‌های هشتگ و پست تازه در روز (نمره با پست در روز) · "
            f"«فرصت» = فروش باسلام به ازای هر هزار رقیب. {fa(weeks)} هفته اندازه‌گیری شده؛ تغییر هفتگی از هفته‌ی دوم معنا دارد.</p>"
            f"<table><tr><th>دسته</th><th>نمره</th><th>قوی در</th><th>فروش هفته باسلام</th><th>رقیب</th><th>فرصت</th>"
            f"<th>دیجی‌کالا</th><th>گوگل</th><th>Ads</th><th>اینستاگرام</th><th>تغییر هفتگی</th><th>مرحله</th><th>قیمت میانه</th><th>فصل ۳ ماه آینده</th></tr>{tr}</table></section>")
    return _shell("رادار دسته‌ها", "شکار دسته", "کدام دسته‌ها بزرگ می‌شوند و کجا رقیب کم است؛ فرصت‌یابی عمیق برای دسته‌های برتر.", body)
