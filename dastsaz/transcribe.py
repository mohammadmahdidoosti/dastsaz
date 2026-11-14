"""Voice note -> Persian text (the supplier sends voice messages). ffmpeg makes an mp3, an audio-capable model on
OpenRouter writes it down. Notes are kept in DATA_DIR/voice_notes so they can be read again later."""
from __future__ import annotations

import base64
import html
import logging
import subprocess
import tempfile
import time
from pathlib import Path

import requests

from . import config as C
from .analyze import OPENROUTER

log = logging.getLogger(__name__)
MODEL = C.secret("TRANSCRIBE_MODEL") or "google/gemini-2.5-flash"
ASK = ("این یک پیامِ صوتیِ فارسی است. فقط متنِ دقیقِ همان چیزی را که گفته می‌شود بنویس، با نقطه‌گذاریِ درست. "
       "چیزی اضافه یا خلاصه نکن و جواب نده؛ اگر بخشی نامفهوم است، [نامفهوم] بنویس.")


def _dir() -> Path:
    d = C.DATA_DIR / "voice_notes"
    d.mkdir(parents=True, exist_ok=True)
    return d


def to_mp3(data: bytes) -> bytes:
    with tempfile.TemporaryDirectory() as t:
        src, dst = Path(t) / "in", Path(t) / "out.mp3"
        src.write_bytes(data)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-ac", "1", "-ar", "16000", "-b:a", "48k", str(dst)],
                       check=True, timeout=120)
        return dst.read_bytes()


def transcribe(data: bytes, key: str | None = None, post=requests.post) -> tuple[str, float]:
    key = key if key is not None else C.secret("OPENROUTER_API_KEY")
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY تنظیم نیست")
    mp3 = to_mp3(data)
    body = {"model": MODEL, "temperature": 0, "max_tokens": 4000,
            "messages": [{"role": "user", "content": [
                {"type": "text", "text": ASK},
                {"type": "input_audio", "input_audio": {"data": base64.b64encode(mp3).decode(), "format": "mp3"}}]}]}
    r = post(OPENROUTER, json=body, timeout=240, headers={"Authorization": f"Bearer {key}", "X-Title": "Dastsaz voice"})
    j = r.json()
    if "error" in j:
        raise RuntimeError(str(j["error"])[:300])
    txt = ((j.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
    return txt.strip(), float((j.get("usage") or {}).get("cost") or 0)


def save(text: str, name: str = "") -> str:
    stamp = time.strftime("%Y%m%d-%H%M%S")
    (_dir() / f"{stamp}.txt").write_text((name + "\n\n" if name else "") + text, encoding="utf-8")
    return stamp


def recent(n: int = 10) -> list[tuple[str, str]]:
    return [(f.stem, f.read_text(encoding="utf-8")) for f in sorted(_dir().glob("*.txt"), reverse=True)[:n]]


def page(result: str = "", err: str = "") -> str:
    items = "".join(f"<details><summary>{html.escape(s)}</summary><pre>{html.escape(t)}</pre></details>" for s, t in recent())
    return f"""<!DOCTYPE html><html lang="fa" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>صدا به متن</title><style>@font-face{{font-family:Vazirmatn;src:url(/static/vazirmatn.woff2) format('woff2')}}
body{{font:16px/1.9 Vazirmatn,Tahoma,sans-serif;max-width:720px;margin:30px auto;padding:0 16px;background:#f4f5f2;color:#1d2433}}
form,.r,details{{background:#fff;border:1px solid #dfe2dc;border-radius:12px;padding:16px;margin:12px 0}}
button{{font:inherit;font-weight:700;background:#b0822a;color:#fff;border:0;border-radius:8px;padding:9px 22px}}
pre{{white-space:pre-wrap;font:inherit}}.err{{color:#a43f55}}</style></head><body>
<h1>صدا به متن</h1><p>پیامِ صوتی (تلگرام، واتس‌اپ، ضبطِ گوشی) را بگذار؛ حدودِ نیم دقیقه طول می‌کشد.</p>
<form method="post" enctype="multipart/form-data" onsubmit="this.querySelector('button').disabled=true;this.querySelector('button').textContent='در حال نوشتن…'">
<input type="file" name="audio" accept="audio/*,.ogg,.oga,.opus,.m4a,.mp3,.wav" required> <button>به متن تبدیل کن</button></form>
{f'<p class="err">{html.escape(err)}</p>' if err else ''}{f'<div class="r"><pre>{html.escape(result)}</pre></div>' if result else ''}
<h2>پیام‌های قبلی</h2>{items or '<p>هنوز چیزی نیست.</p>'}</body></html>"""
