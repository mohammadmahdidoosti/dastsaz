"""Google Ads Keyword Planner export, uploaded by hand once a month (Keyword Planner -> download -> .csv).
Iran can't be targeted, so Persian words show the diaspora + Afghanistan + Tajikistan; English words show
foreign markets. We keep each upload, read monthly searches per keyword, and show the change.
No API, no secrets; Claude's tokens are not needed to read it."""
from __future__ import annotations

import csv
import datetime as dt
import io
import json
import re

from . import config as C


def _dir():
    d = C.DATA_DIR / "ads"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _num(x):
    x = str(x or "").replace(",", "").replace("%", "").replace("−", "-").strip()
    if not x or x in ("-", "–"):
        return None
    try:
        return float(x)
    except ValueError:
        m = re.match(r"([\d.]+)\s*[KkMm]?", x)
        return float(m.group(1)) if m else None


def parse(raw: bytes) -> list[dict]:
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        text = raw.decode("utf-16")
    else:
        text = raw.decode("utf-8-sig", errors="replace")
    lines = text.splitlines()
    head = next((i for i, l in enumerate(lines) if l.lower().startswith(("keyword\t", "keyword,", '"keyword"'))), None)
    if head is None:
        return []
    body = "\n".join(lines[head:])
    delim = "\t" if "\t" in lines[head] else ","
    rows = list(csv.DictReader(io.StringIO(body), delimiter=delim))
    out = []
    for r in rows:
        kw = (r.get("Keyword") or "").strip()
        if not kw:
            continue
        months = {k.split(":", 1)[1].strip(): _num(v) for k, v in r.items() if k and k.startswith("Searches:")}
        out.append({"keyword": kw, "avg": _num(r.get("Avg. monthly searches")),
                    "three_month": _num(r.get("Three month change")), "yoy": _num(r.get("YoY change")),
                    "competition": (r.get("Competition") or "").strip(), "months": months})
    return out


def save(raw: bytes) -> int:
    rows = parse(raw)
    if rows:
        f = _dir() / f"{C.today().isoformat()}.json"
        f.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    return len(rows)


def latest() -> tuple[str, list[dict]]:
    fs = sorted(_dir().glob("*.json"))
    return (fs[-1].stem, json.loads(fs[-1].read_text(encoding="utf-8"))) if fs else ("", [])
