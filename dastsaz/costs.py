"""Cost ledger per run (same idea as the Caravan crawler's costs.py): one CSV line per paid step."""
from __future__ import annotations

import csv
import logging
import time
from pathlib import Path

log = logging.getLogger(__name__)
FILE = "costs.csv"
COLS = ["time", "step", "units", "usd", "estimated", "note"]


def add(d: Path, step: str, units: int, usd: float, note: str = "", estimated: bool = False) -> None:
    try:
        p = Path(d) / FILE
        new = not p.exists()
        with p.open("a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, COLS)
            if new:
                w.writeheader()
            w.writerow({"time": time.strftime("%Y-%m-%d %H:%M"), "step": step, "units": int(units),
                        "usd": f"{float(usd):.4f}", "estimated": "yes" if estimated else "", "note": note})
        log.info("COST %s: %d unit(s), $%.4f %s", step, units, usd, note)
    except Exception as e:  # noqa: BLE001 - a missing ledger line never stops a step
        log.warning("cost not written (%s): %s", step, e)


def summary(d: Path) -> dict:
    p = Path(d) / FILE
    steps: dict[str, dict] = {}
    total = 0.0
    if p.exists():
        with p.open(encoding="utf-8") as f:
            for r in csv.DictReader(f):
                s = steps.setdefault(r["step"], {"units": 0, "usd": 0.0})
                s["units"] += int(r["units"] or 0)
                s["usd"] = round(s["usd"] + float(r["usd"] or 0), 4)
                total += float(r["usd"] or 0)
    return {"steps": steps, "usd": round(total, 4)}
