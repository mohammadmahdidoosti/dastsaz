#!/usr/bin/env python3
"""Dastsaz web page: list of trend reports, a button to make a new one, and its progress.

Environment (entered by the owner in Coolify, never in the repo):
  APP_PASSWORD        password for the whole page (any username)
  APIFY_TOKEN         Apify API token (Etsy)
  OPENROUTER_API_KEY  OpenRouter key (translation + style classification)
  DATA_DIR            /data in Coolify (a persistent volume)
  PORT                default 8000
"""
from __future__ import annotations

import base64
import hmac
import html
import json
import logging
import os
import re
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from dastsaz import config as C
from dastsaz import ads, categories, deepdive, designs, influencers, pinterest, lab_seed, guard, schedule, lab, needs, page, pipeline, snapshot, telegram, voice

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
logging.getLogger("urllib3").setLevel(logging.WARNING)
log = logging.getLogger("app")
APP_PASSWORD = os.environ.get("APP_PASSWORD", "")
STATIC = Path(__file__).resolve().parent / "static"
NAME = re.compile(r"^[\w\-]{1,60}$")
IMG = re.compile(r"^[0-9a-f]{8}\.png$")
PIMG = re.compile(r"^[0-9a-f]{12}\.jpg$")
PIN = re.compile(r"^[\w\-]{1,120}$")
STEP_FA = {"wait": "منتظر", "basalam": "باسلام", "digikala": "دیجی‌کالا", "etsy": "اتسی", "ai": "هوش مصنوعی", "expand": "فرصت‌یابی", "testlist": "لیست آزمایش", "trends": "گوگل ترندز", "suggest": "پیشنهادهای جست‌وجو",
           "reviews": "نظر خریداران", "makers": "سازنده‌ها", "snapshot": "عکس هفتگی فروش",
           "voice": "صدای مشتری", "needs": "نیازهای کادو", "telegram": "تلگرام", "radar": "رادار دسته‌ها",
           "radar_trends": "گوگلِ دسته‌ها", "radar_ig": "اینستاگرامِ دسته‌ها", "twitter": "توییتر کادو", "translation_test": "تست ترجمه‌ی دسته‌ها", "lab_seed": "ثبت طرح‌های اول", "designs": "ماشین طراحی", "designs_sample": "۵ طرح نمونه", "designs_redraw": "تصویر طرح‌ها", "designs_v2": "طراحی دور دوم", "deepdive": "بررسی دسته‌های کم‌رقیب", "pinterest": "پینترست هفتگی", "twitter_ideas": "ایده‌های توییتر", "twitter_ideas_recheck": "بررسی دوباره‌ی بازار ایده‌ها", "influencers": "پیدا کردن اینفلوئنسر",
           "report": "گزارش"}


class Job:
    def __init__(self):
        self.lock = threading.Lock()
        self.state = {"running": False, "run": "", "step": "", "done": 0, "total": 0, "note": "",
                      "error": "", "started": 0, "ended": 0}

    def update(self, **k):
        with self.lock:
            self.state.update(k)

    def start(self, name: str, only: str = "", task=None) -> str:
        """One job at a time (they all read Basalam/Digikala slowly). task: a function(progress) instead of a report."""
        with self.lock:
            if self.state["running"]:
                return "یک کار دیگر در حال اجراست؛ بعد از تمام شدنش دوباره بزنید"
            self.state.update(running=True, run=name, step="", done=0, total=0, note="", error="",
                              started=time.time(), ended=0)
        threading.Thread(target=self._go, args=(name, only, task), daemon=True).start()
        return ""

    def _go(self, name, only, task=None):
        try:
            if task:
                self.update(step=name)
                task(lambda i, t: self.update(done=i, total=t))
                self.update(running=False, ended=time.time(), step="done", note="آماده است")
                return
            pipeline.run(name, status=self.update, only=only)
            self.update(running=False, ended=time.time(), step="done", note="گزارش آماده است")
        except Exception as e:  # noqa: BLE001
            log.error("run %s failed: %s\n%s", name, e, traceback.format_exc())
            self.update(running=False, ended=time.time(), error=str(e)[:400])


JOB = Job()

PAGE = """<!DOCTYPE html><html lang="fa" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>دست‌ساز</title>
<style>@font-face{font-family:Vazirmatn;src:url(/static/vazirmatn.woff2) format('woff2');font-weight:100 900}
:root{--ink:#1d2433;--soft:#5b6476;--paper:#f4f5f2;--line:#dfe2dc;--gold:#b0822a;--turq:#13877f;--lapis:#2f4b85}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.85 Vazirmatn,Tahoma,sans-serif}
header{background:var(--lapis);color:#fff;padding:34px 0 30px}.w{max-width:820px;margin:auto;padding:0 20px}
h1{margin:0;font-size:30px;font-weight:800}header p{margin:6px 0 0;color:#dfe5f3}
.stones{display:flex;gap:6px;margin-top:14px}.stones i{width:12px;height:12px;border-radius:50%;display:block}
.now{background:#fff;border:1px solid var(--line);border-radius:12px;padding:18px 20px;margin:-18px 0 26px;
box-shadow:0 10px 30px rgba(20,30,60,.08)}
.now .st{font-weight:700}.err{color:#a43f55}.muted{color:var(--soft);font-size:13px}
button{font:inherit;font-weight:700;background:var(--gold);color:#fff;border:0;border-radius:8px;padding:9px 20px;cursor:pointer}
button:disabled{background:#c9ccc6;cursor:default}button:focus-visible,a:focus-visible{outline:2px solid var(--lapis);outline-offset:2px}
.prog{height:6px;background:#eceee9;border-radius:3px;margin:10px 0 4px;overflow:hidden}
.prog i{display:block;height:100%;background:var(--turq);width:0;transition:width .4s}
h2{font-size:19px;margin:0 0 10px}
.r{display:flex;justify-content:space-between;align-items:center;gap:12px;background:#fff;border:1px solid var(--line);
border-radius:10px;padding:12px 16px;margin-bottom:8px}
.r a.t{font-weight:800;font-size:16px;color:var(--ink);text-decoration:none}.r a.t:hover{color:var(--lapis)}
.r .l a{font-size:13px;color:var(--lapis);margin-right:12px}
.tools{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px;margin:0 0 14px}
.tool{background:#fff;border:1px solid var(--line);border-radius:10px;padding:12px 14px;text-decoration:none;color:var(--ink)}
.tool b{display:block;color:var(--lapis)}.tool span{font-size:13px;color:var(--soft)}
button.sm{font-size:13px;padding:4px 12px;background:var(--turq);margin:4px 2px}</style></head>
<body><header><div class="w"><h1>دست‌ساز</h1><p>ترند جواهرات از اتسی، باسلام، دیجی‌کالا و گوگل؛ برای انتخاب طرح و صحبت با تولیدکننده.</p>
<div class="stones"><i style="background:#b0822a"></i><i style="background:#13877f"></i><i style="background:#9fb5e3"></i></div></div></header>
<main class="w"><div class="now"><div id="st">...</div><div class="prog" id="pg" hidden><i></i></div>
<p style="margin:12px 0 0"><button id="go" onclick="go()">ساختن گزارش تازه</button>
<span class="muted">حدود نیم ساعت؛ حدود ۱٫۶ دلار.</span></p></div>
<div class="tools"><a class="tool" href="lab"><b>آزمایشگاه</b><span>ثبت آزمایش‌ها، تصمیم برنده/کنار، سهم نمایش</span></a>
<a class="tool" href="voice"><b>صدای مشتری</b><span>شکایت‌ها و خواسته‌های خریداران</span></a>
<a class="tool" href="needs"><b>نیازهای کادو</b><span>مردم برای چه کسی و چه مناسبتی دنبال کادو هستند</span></a>
<a class="tool" href="radar"><b>رادار دسته‌ها</b><span>کدام دسته‌ها بزرگ می‌شوند</span></a>
<a class="tool" href="telegram"><b>تلگرام</b><span>کانال‌ها چه طرحی را جلو می‌برند</span></a>
<a class="tool" href="ads"><b>گوگل ادز</b><span>بارگذاری خروجی ماهانه</span></a>
<a class="tool" href="backtest"><b>دقت سیستم</b><span>آزمون روی گذشته</span></a></div>
<p class="muted">اجرای دستی (هر کدام جدا؛ با هم اجرا نمی‌شوند):
<button class="sm" onclick="task('snapshot')">عکس هفتگی فروش (۶ دقیقه)</button>
<button class="sm" onclick="task('voice')">صدای مشتری (۲۰ دقیقه)</button>
<button class="sm" onclick="task('needs')">نیازهای کادو (۵ دقیقه)</button>
<button class="sm" onclick="task('telegram')">تلگرام</button>
<button class="sm" onclick="task('radar')">رادار دسته‌ها (حدود یک ساعت)</button>
<button class="sm" onclick="task('pinterest')">پینترست هفتگی (حدود ۰٫۷ دلار)</button>
<button class="sm" onclick="task('radar_ig')">اینستاگرامِ ۶۰ دسته‌ی بالا (حدود ۱٫۵ دلار)</button>
<button class="sm" onclick="task('radar_trends')">گوگلِ دسته‌ها (ماهانه، حدود ۰٫۵ دلار)</button></p>
<h2>گزارش‌ها</h2><div id="list">...</div></main>
<script>
const F=n=>String(n).replace(/[0-9]/g,d=>'۰۱۲۳۴۵۶۷۸۹'[d]);
async function load(){const s=await (await fetch('api/status')).json();const j=s.job;let t;
if(j.running){t=`<span class=st>در حال ساخت «${j.run}»</span> — ${s.step_fa}${j.total?` (${F(j.done)} از ${F(j.total)})`:''}`+
(j.note?`<div class=muted>${j.note}</div>`:'');}
else if(j.error){t=`<span class="st err">ساخت «${j.run}» متوقف شد:</span> ${j.error}`}
else t=j.run?`<span class=st>گزارش «${j.run}» آماده است.</span>`:'<span class=st>آماده برای گزارش تازه.</span>';
if(s.guard)t+=`<div class=muted>منتظر: ${s.guard}</div>`;
document.getElementById('st').innerHTML=t;document.getElementById('go').disabled=j.running;
const pg=document.getElementById('pg');pg.hidden=!(j.running&&j.total);if(j.total)pg.firstChild.style.width=(100*j.done/j.total)+'%';
document.getElementById('list').innerHTML=s.runs.map(r=>r.report?`<div class=r><div><a class=t href="report/${r.name}" target=_blank>${r.name}</a>
<div class=muted>هزینه ${F(r.usd)} دلار</div></div><div class=l><a href="csv/${r.name}">محصولات (اکسل)</a>
<a href="csv/${r.name}?f=opportunities">فرصت‌ها (اکسل)</a></div></div>`:`<div class=r><span>${r.name}</span><span class=muted>ناتمام</span></div>`).join('')
||'<p class=muted>هنوز گزارشی ساخته نشده. «ساختن گزارش تازه» را بزنید.</p>'}
async function task(n){const r=await (await fetch('api/task?name='+n,{method:'POST'})).json();if(r.error)alert(r.error);load()}
async function go(){const r=await (await fetch('api/run',{method:'POST'})).json();if(r.error)alert(r.error);load()}
load();setInterval(load,10000);
</script></body></html>"""


class H(BaseHTTPRequestHandler):
    def log_message(self, fmt, *a):
        pass

    def _authed(self) -> bool:
        if not APP_PASSWORD:
            return True
        h = self.headers.get("Authorization", "")
        if not h.startswith("Basic "):
            return False
        try:
            pw = base64.b64decode(h[6:]).decode("utf-8").split(":", 1)[1]
        except Exception:  # noqa: BLE001
            return False
        return hmac.compare_digest(pw.encode(), APP_PASSWORD.encode())

    def _send(self, code, body: bytes, ctype="text/html; charset=utf-8", extra=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj, ensure_ascii=False).encode(), "application/json; charset=utf-8")

    def _gate(self) -> bool:
        if self._authed():
            return True
        self._send(401, b"login", "text/plain", {"WWW-Authenticate": 'Basic realm="dastsaz"'})
        return False

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/healthz":
            return self._send(200, b"ok", "text/plain")
        if u.path == "/static/vazirmatn.woff2":           # the report font (no outside font server needed in Iran)
            return self._send(200, (STATIC / "vazirmatn.woff2").read_bytes(), "font/woff2",
                              {"Cache-Control": "public, max-age=2592000"})
        parts = [p for p in u.path.split("/") if p]
        if len(parts) >= 2 and parts[0] == "s":                 # supplier page: secret link, no password
            if not hmac.compare_digest(parts[1].encode(), designs.token().encode()):
                return self._send(404, "پیدا نشد".encode(), "text/plain; charset=utf-8")
            if len(parts) == 4 and parts[2] == "img" and IMG.match(parts[3]):
                return self._img(parts[3])
            if len(parts) == 3 and parts[2] == "people":
                return self._send(200, page.influencers_page(influencers.latest(), f"/s/{parts[1]}/person", supplier=True).encode())
            if len(parts) == 3 and parts[2] == "ideas":
                return self._send(200, page.tw_ideas_page(needs.twitter_ideas_latest(), supplier=True).encode())
            if len(parts) == 3 and parts[2] == "pins":
                return self._send(200, page.pins_page(pinterest.latest(), f"/s/{parts[1]}/pimg",
                                                      f"/s/{parts[1]}/pin", supplier=True).encode())
            if len(parts) == 4 and parts[2] == "pimg" and PIMG.match(parts[3]):
                return self._pimg(parts[3])
            if len(parts) == 2:
                return self._send(200, page.supplier_page(designs.load(), designs.CATEGORIES, parts[1],
                                                          "ok" in parse_qs(u.query)).encode())
        if not self._gate():
            return
        if not parts:
            return self._send(200, PAGE.encode())
        if parts == ["designs"]:
            lf = designs._dir() / "last_run.json"
            host = self.headers.get("Host", "")
            return self._send(200, page.designs_page(
                designs.load(), designs.counts(), designs.CATEGORIES, f"https://{host}/s/{designs.token()}",
                json.loads(lf.read_text(encoding="utf-8")) if lf.exists() else None).encode())
        if parts == ["people"]:
            return self._send(200, page.influencers_page(influencers.latest(), "/person").encode())
        if parts == ["tw-ideas"]:
            return self._send(200, page.tw_ideas_page(needs.twitter_ideas_latest()).encode())
        if parts == ["pins"]:
            return self._send(200, page.pins_page(pinterest.latest(), "/pimg", "/pin").encode())
        if len(parts) == 2 and parts[0] == "pimg" and PIMG.match(parts[1]):
            return self._pimg(parts[1])
        if len(parts) == 3 and parts[:2] == ["designs", "img"] and IMG.match(parts[2]):
            return self._img(parts[2])
        if parts == ["api", "status"]:
            j = dict(JOB.state)
            q = parse_qs(u.query)
            g = guard.check() if "guard" in q or not j["running"] else ""
            return self._json({"job": j, "step_fa": STEP_FA.get(j["step"], j["step"]), "runs": pipeline.runs(),
                               "guard": g})
        if parts == ["lab"]:
            return self._send(200, page.lab_page(lab.board(), snapshot.changes(), len(snapshot.history()),
                                                 _ideas()).encode())
        if parts == ["radar"]:
            tf = C.DATA_DIR / "backtest" / "trends_categories.json"
            import json as _j
            return self._send(200, page.radar_page(categories.board(), len(categories.categories(1)),
                                                   len(categories.history()),
                                                   _j.loads(tf.read_text(encoding="utf-8")) if tf.exists() else None).encode())
        if parts == ["ads"]:
            return self._send(200, page.ads_page(*ads.latest()).encode())
        if parts == ["telegram"]:
            motifs = _designs()
            return self._send(200, page.telegram_page(telegram.channels(),
                                                      {c: len(p) for c, p in telegram.posts().items()},
                                                      telegram.recent(motifs)).encode())
        if parts == ["voice"]:
            return self._send(200, page.voice_page(voice.latest()).encode())
        if parts == ["needs"]:
            return self._send(200, page.needs_page(needs.latest()).encode())
        if parts == ["backtest"]:
            f = C.DATA_DIR / "backtest" / "report.html"
            return self._send(200, f.read_bytes()) if f.exists() else self._send(404, "هنوز آزمونی اجرا نشده".encode(), "text/plain; charset=utf-8")
        if len(parts) == 2 and parts[0] in ("report", "csv") and NAME.match(parts[1]):
            d = C.DATA_DIR / "runs" / parts[1]
            if parts[0] == "report" and (d / "report.html").exists():
                return self._send(200, (d / "report.html").read_bytes())
            f = "opportunities" if parse_qs(u.query).get("f") == ["opportunities"] else "products"
            if parts[0] == "csv" and (d / f"{f}.csv").exists():
                return self._send(200, (d / f"{f}.csv").read_bytes(), "text/csv; charset=utf-8",
                                  {"Content-Disposition": f'attachment; filename="dastsaz-{parts[1]}-{f}.csv"'})
        return self._send(404, "پیدا نشد".encode(), "text/plain; charset=utf-8")

    def _img(self, name: str):
        f = designs._dir() / "img" / name
        if not f.exists():
            return self._send(404, b"", "text/plain")
        raw = f.read_bytes()
        return self._send(200, raw, "image/jpeg" if raw[:2] == b"\xff\xd8" else "image/png",
                          {"Cache-Control": "public, max-age=86400"})

    def _pimg(self, name: str):
        f = pinterest._dir() / "img" / name
        if not f.exists():
            return self._send(404, b"", "text/plain")
        return self._send(200, f.read_bytes(), "image/jpeg", {"Cache-Control": "public, max-age=604800"})

    def _upload(self) -> bytes:
        """The one file of a multipart form (Keyword Planner csv, a few hundred KB at most)."""
        n = min(int(self.headers.get("Content-Length") or 0), 5_000_000)
        raw = self.rfile.read(n) if n else b""
        m = re.search(rb"boundary=([^;]+)", (self.headers.get("Content-Type") or "").encode())
        if not m:
            return b""
        for part in raw.split(b"--" + m.group(1).strip(b'"')):
            if b"filename=" in part and b"\r\n\r\n" in part:
                return part.split(b"\r\n\r\n", 1)[1].rsplit(b"\r\n", 1)[0]
        return b""

    def _form(self) -> dict:
        n = min(int(self.headers.get("Content-Length") or 0), 20000)
        raw = self.rfile.read(n).decode("utf-8", "replace") if n else ""
        return {k: v[0] for k, v in parse_qs(raw).items()}

    def _back(self, to="/lab"):
        self._send(303, b"", "text/plain", {"Location": to})

    def do_POST(self):
        u = urlparse(self.path)
        parts = [p for p in u.path.split("/") if p]
        if (len(parts) == 4 and parts[0] == "s" and parts[2] == "person" and PIN.match(parts[3])
                and hmac.compare_digest(parts[1].encode(), designs.token().encode())):
            influencers.pick(parts[3], self._form().get("on") == "1")
            return self._back(f"/s/{parts[1]}/people")
        if (len(parts) == 4 and parts[0] == "s" and parts[2] == "pin" and PIN.match(parts[3])
                and hmac.compare_digest(parts[1].encode(), designs.token().encode())):
            pinterest.like(parts[3], self._form().get("on") == "1")
            return self._back(f"/s/{parts[1]}/pins")
        if len(parts) == 3 and parts[0] == "s" and hmac.compare_digest(parts[1].encode(), designs.token().encode()):
            f = self._form()
            designs.answer(parts[2], f.get("can", ""), f.get("cost", ""), f.get("days", ""), f.get("note", ""))
            return self._back(f"/s/{parts[1]}?ok=1")
        if not self._gate():
            return
        if len(parts) == 2 and parts[0] == "person" and PIN.match(parts[1]):
            influencers.pick(parts[1], self._form().get("on") == "1")
            return self._back("/people")
        if len(parts) == 2 and parts[0] == "pin" and PIN.match(parts[1]):
            pinterest.like(parts[1], self._form().get("on") == "1")
            return self._back("/pins")
        if parts == ["designs", "lab"]:
            designs.to_lab()
            return self._back("/designs")
        if parts == ["ads", "upload"]:
            ads.save(self._upload())
            return self._back("/ads")
        if parts == ["telegram", "channels"]:
            telegram.set_channels(self._form().get("channels", "").split())
            return self._back("/telegram")
        if parts == ["lab", "add"]:
            f = self._form()
            if f.get("name", "").strip():
                price = f.get("price", "").strip()
                lab.add(f["name"], f.get("channel", "other"), f.get("source", "manual"),
                        int(price) if price.isdigit() else None, f.get("query", ""), f.get("stage", "pretest"),
                        f.get("control") == "1", f.get("note", ""), f.get("tags", ""))
            return self._back()
        if len(parts) == 3 and parts[:2] == ["lab", "update"] and NAME.match(parts[2]):
            f = self._form()
            lab.update(parts[2], {k: f.get(k) if str(f.get(k, "")).isdigit() else 0 for k in lab.FIELDS},
                       f.get("close", ""))
            return self._back()
        if u.path == "/api/task":
            name = (parse_qs(u.query).get("name") or [""])[0]
            fn = {"snapshot": lambda p: snapshot.take(progress=p), "voice": lambda p: voice.run(progress=p),
                  "needs": lambda p: needs.run(progress=p), "telegram": lambda p: telegram.run(progress=p),
                  "radar": lambda p: categories.run(progress=p), "radar_trends": lambda p: categories.trends(), "radar_ig": lambda p: categories.instagram(), "twitter": lambda p: needs.twitter(), "translation_test": lambda p: categories.translation_test(progress=p),
                  "lab_seed": lambda p: lab_seed.seed(), "designs": lambda p: designs.generate(progress=p),
                  "designs_sample": lambda p: designs.generate(per=5, cats=["necklace"], progress=p),
                  "designs_redraw": lambda p: designs.redraw(), "designs_v2": lambda p: designs.generate_v2(progress=p), "designs_shrink": lambda p: designs.shrink_all(), "deepdive": lambda p: deepdive.run(progress=p), "pinterest": lambda p: pinterest.run(), "twitter_ideas": lambda p: needs.twitter_ideas(progress=p), "twitter_ideas_recheck": lambda p: needs.twitter_ideas(progress=p, reuse=True), "influencers": lambda p: influencers.run(progress=p), "influencers_niches": lambda p: influencers.run(progress=p, niches=influencers.NICHES, with_twitter=True, max_usd=2.5, per_tag=20)}.get(name)
            if not fn:
                return self._json({"error": "نامعتبر"}, 400)
            err = JOB.start(name, task=fn)
            return self._json({"error": err} if err else {"ok": True})
        if u.path == "/api/run":
            q = parse_qs(u.query)
            name = (q.get("name") or [time.strftime("trial-%Y%m%d-%H%M")])[0]
            if not NAME.match(name):
                return self._json({"error": "نام نامعتبر"}, 400)
            err = JOB.start(name, (q.get("only") or [""])[0])
            return self._json({"error": err} if err else {"ok": True, "run": name})
        return self._json({"error": "not found"}, 404)


def _designs() -> list[str]:
    import json as _j
    runs = sorted((C.DATA_DIR / "runs").glob("*/opportunities.json"), key=lambda p: p.stat().st_mtime)
    return [o["q"] for o in _j.loads(runs[-1].read_text(encoding="utf-8"))] if runs else []


def _ideas() -> str:
    n, v = needs.latest() or {}, voice.latest() or {}
    try:
        tg = telegram.recent(_designs())
    except Exception:  # noqa: BLE001
        tg = []
    return page.ideas_box(n.get("ideas") or [], v.get("themes") or [], tg)


def main():
    C.DATA_DIR.mkdir(parents=True, exist_ok=True)
    port = int(os.environ.get("PORT", "8000"))
    log.info("dastsaz on :%d, data in %s, password %s", port, C.DATA_DIR, "set" if APP_PASSWORD else "NOT SET")
    schedule.start(lambda name, fn: JOB.start(name, task=fn),
                   {"snapshot": lambda p: snapshot.take(progress=p), "radar": lambda p: categories.run(progress=p),
                    "pinterest": lambda p: pinterest.run()})
    ThreadingHTTPServer(("0.0.0.0", port), H).serve_forever()


if __name__ == "__main__":
    main()
