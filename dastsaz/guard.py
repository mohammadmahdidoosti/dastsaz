"""Keeps Dastsaz out of the Caravan Sanat crawler's way.

Before (and during) a crawl we read the crawler's public, read-only /api/status. We wait while its
crawl or health lane runs or its autopilot (night crawl) has a batch, and we never start in the quiet
night hours. If the status can't be read, we wait too (better late than in the way).
"""
from __future__ import annotations

import datetime as dt
import logging
import time
from zoneinfo import ZoneInfo

import requests

from . import config as C

log = logging.getLogger(__name__)


def quiet_now(now: dt.datetime | None = None) -> bool:
    if C.QUIET_FROM == C.QUIET_TO:
        return False
    h = (now or dt.datetime.now(ZoneInfo(C.TIMEZONE))).hour
    if C.QUIET_FROM <= C.QUIET_TO:
        return C.QUIET_FROM <= h < C.QUIET_TO
    return h >= C.QUIET_FROM or h < C.QUIET_TO


def caravan_busy(status: dict) -> str:
    """'' when free, otherwise a short reason."""
    lanes = status.get("lanes") or {}
    for lane in ("crawl", "health"):
        if (lanes.get(lane) or {}).get("running"):
            return f"کراولر کاروان صنعت مشغول است ({lane})"
    ap = status.get("autopilot") or {}
    if ap.get("current"):
        return "کراول شبانه‌ی کاروان صنعت در حال اجراست"
    return ""


def check() -> str:
    if not C.GUARD:
        return ""
    if quiet_now():
        return f"ساعت آرام شب ({C.QUIET_FROM}:00 تا {C.QUIET_TO}:00 تهران)"
    try:
        r = requests.get(C.CARAVAN_STATUS_URL, timeout=15)
        r.raise_for_status()
        return caravan_busy(r.json())
    except Exception as e:  # noqa: BLE001
        return f"وضعیت کراولر کاروان خوانده نشد ({type(e).__name__})"


def wait_free(on_wait=None, every: int = 300, max_hours: float = 12) -> None:
    """Blocks until it's fine to crawl. Raises after max_hours."""
    end = time.time() + max_hours * 3600
    while True:
        why = check()
        if not why:
            return
        log.info("waiting: %s", why)
        if on_wait:
            on_wait(why)
        if time.time() > end:
            raise RuntimeError("بیش از حد منتظر ماندیم: " + why)
        time.sleep(every)
