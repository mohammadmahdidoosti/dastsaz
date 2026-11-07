"""Weekly automatic runs inside the app (no outside scheduler): the sales photo on Saturday night and the category
radar on Tuesday night (Tehran time), spread apart so Basalam is read gently. Only reading, free.
Off by setting AUTO=0. A run is skipped (and retried later) while another job runs."""
from __future__ import annotations

import datetime as dt
import json
import logging
import threading
import time
from zoneinfo import ZoneInfo

from . import config as C

log = logging.getLogger(__name__)
TZ = ZoneInfo("Asia/Tehran")
PLAN = {"snapshot": 5, "radar": 1, "pinterest": 6}   # weekday (Mon=0): Saturday, Tuesday, Sunday
HOUR = 2                                     # after 02:00 Tehran


def _f():
    return C.DATA_DIR / "schedule.json"


def done() -> dict:
    f = _f()
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}


def due(now: dt.datetime, last: dict) -> list[str]:
    out = []
    for name, wd in PLAN.items():
        if now.weekday() != wd or now.hour < HOUR:
            continue
        if last.get(name) != now.date().isoformat():
            out.append(name)
    return out


def loop(start_job, tasks: dict, every: int = 900):
    """start_job(name, fn) -> '' if started. tasks: name -> fn(progress)."""
    while True:
        try:
            if C.secret("AUTO") != "0":
                now = dt.datetime.now(TZ)
                last = done()
                for name in due(now, last):
                    if not start_job(name, tasks[name]):
                        last[name] = now.date().isoformat()
                        _f().write_text(json.dumps(last), encoding="utf-8")
                        log.info("weekly %s started", name)
                    break                     # one at a time
        except Exception as e:  # noqa: BLE001
            log.warning("schedule: %s", e)
        time.sleep(every)


def start(start_job, tasks: dict) -> None:
    threading.Thread(target=loop, args=(start_job, tasks), daemon=True).start()
