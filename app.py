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
from urllib.parse import parse_qs, urlparse

from dastsaz import config as C
from dastsaz import guard, pipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
logging.getLogger("urllib3").setLevel(logging.WARNING)
log = logging.getLogger("app")
APP_PASSWORD = os.environ.get("APP_PASSWORD", "")
NAME = re.compile(r"^[\w\-]{1,60}$")
STEP_FA = {"wait": "منتظر", "basalam": "باسلام", "etsy": "اتسی", "ai": "هوش مصنوعی", "report": "گزارش"}


class Job:
    def __init__(self):
        self.lock = threading.Lock()
        self.state = {"running": False, "run": "", "step": "", "done": 0, "total": 0, "note": "",
                      "error": "", "started": 0, "ended": 0}

    def update(self, **k):
        with self.lock:
            self.state.update(k)

    def start(self, name: str, only: str = "") -> str:
        with self.lock:
            if self.state["running"]:
                return "یک گزارش در حال ساخت است"
            self.state.update(running=True, run=name, step="", done=0, total=0, note="", error="",
                              started=time.time(), ended=0)
        threading.Thread(target=self._go, args=(name, only), daemon=True).start()
        return ""

    def _go(self, name, only):
        try:
            pipeline.run(name, status=self.update, only=only)
            self.update(running=False, ended=time.time(), step="done", note="گزارش آماده است")
        except Exception as e:  # noqa: BLE001
            log.error("run %s failed: %s\n%s", name, e, traceback.format_exc())
            self.update(running=False, ended=time.time(), error=str(e)[:400])


JOB = Job()

PAGE = """<!DOCTYPE html><html lang="fa" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>دست‌ساز</title>
<style>body{font-family:Vazirmatn,Tahoma,sans-serif;background:#faf7f2;color:#2b2622;max-width:760px;margin:auto;padding:20px;line-height:1.9}
.box{background:#fff;border:1px solid #ece3d6;border-radius:12px;padding:16px;margin:14px 0}
button{font:inherit;background:#b8860b;color:#fff;border:0;border-radius:8px;padding:8px 18px;cursor:pointer}
button:disabled{background:#ccc}a{color:#8a5a00}.err{color:#b00}.muted{color:#8a7f74;font-size:13px}</style></head>
<body><h1>دست‌ساز — گزارش ترند جواهرات</h1>
<div class="box" id="st">...</div>
<div class="box"><button id="go" onclick="go()">ساختن گزارش جدید</button>
<p class="muted">کراول باسلام آرام است؛ اتسی روی سرورهای Apify اجرا می‌شود.</p></div>
<div class="box"><h3>گزارش‌ها</h3><div id="list">...</div></div>
<script>
const F=n=>String(n).replace(/[0-9]/g,d=>'۰۱۲۳۴۵۶۷۸۹'[d]);
async function load(){const s=await (await fetch('api/status')).json();const j=s.job;
let t=j.running?`در حال ساخت «${j.run}» — مرحله: ${s.step_fa}${j.total?` (${F(j.done)} از ${F(j.total)})`:''}<br><span class=muted>${j.note||''}</span>`
:(j.error?`<span class=err>خطا در «${j.run}»: ${j.error}</span>`:(j.run?`آخرین گزارش «${j.run}» آماده شد.`:'آماده.'));
if(s.guard)t+=`<br><span class=muted>منتظر: ${s.guard}</span>`;
document.getElementById('st').innerHTML=t;document.getElementById('go').disabled=j.running;
document.getElementById('list').innerHTML=s.runs.map(r=>r.report?`<p><a href="report/${r.name}" target=_blank>${r.name}</a> — هزینه ${F(r.usd)} دلار · <a href="csv/${r.name}">فایل اکسل (CSV)</a></p>`:`<p>${r.name} (ناتمام)</p>`).join('')||'هنوز گزارشی نیست.'}
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
        if not self._gate():
            return
        parts = [p for p in u.path.split("/") if p]
        if not parts:
            return self._send(200, PAGE.encode())
        if parts == ["api", "status"]:
            j = dict(JOB.state)
            q = parse_qs(u.query)
            g = guard.check() if "guard" in q or not j["running"] else ""
            return self._json({"job": j, "step_fa": STEP_FA.get(j["step"], j["step"]), "runs": pipeline.runs(),
                               "guard": g})
        if len(parts) == 2 and parts[0] in ("report", "csv") and NAME.match(parts[1]):
            d = C.DATA_DIR / "runs" / parts[1]
            if parts[0] == "report" and (d / "report.html").exists():
                return self._send(200, (d / "report.html").read_bytes())
            if parts[0] == "csv" and (d / "products.csv").exists():
                return self._send(200, (d / "products.csv").read_bytes(), "text/csv; charset=utf-8",
                                  {"Content-Disposition": f'attachment; filename="dastsaz-{parts[1]}.csv"'})
        return self._send(404, "پیدا نشد".encode(), "text/plain; charset=utf-8")

    def do_POST(self):
        if not self._gate():
            return
        u = urlparse(self.path)
        if u.path == "/api/run":
            q = parse_qs(u.query)
            name = (q.get("name") or [time.strftime("trial-%Y%m%d-%H%M")])[0]
            if not NAME.match(name):
                return self._json({"error": "نام نامعتبر"}, 400)
            err = JOB.start(name, (q.get("only") or [""])[0])
            return self._json({"error": err} if err else {"ok": True, "run": name})
        return self._json({"error": "not found"}, 404)


def main():
    C.DATA_DIR.mkdir(parents=True, exist_ok=True)
    port = int(os.environ.get("PORT", "8000"))
    log.info("dastsaz on :%d, data in %s, password %s", port, C.DATA_DIR, "set" if APP_PASSWORD else "NOT SET")
    ThreadingHTTPServer(("0.0.0.0", port), H).serve_forever()


if __name__ == "__main__":
    main()
