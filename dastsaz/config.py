"""Settings. Secrets come only from environment variables (entered by the owner in Coolify)."""
from __future__ import annotations

import os
from pathlib import Path

DATA_DIR = Path(os.environ.get("DATA_DIR", Path(__file__).resolve().parent.parent / "data")).resolve()

# Caravan Sanat crawler: we only READ its public status, never touch it
CARAVAN_STATUS_URL = os.environ.get("CARAVAN_STATUS_URL", "https://crawler.caravansanat.com/api/status")

# Dastsaz never crawls in these Tehran hours (the Caravan night crawl's time)
QUIET_FROM = int(os.environ.get("QUIET_FROM", "0"))     # 00:00
QUIET_TO = int(os.environ.get("QUIET_TO", "9"))         # 09:00
TIMEZONE = "Asia/Tehran"

# AI through OpenRouter (same service the Caravan crawler uses)
AI_MODEL = os.environ.get("AI_MODEL", "deepseek/deepseek-v4.1-flash")
AI_WORKERS = int(os.environ.get("AI_WORKERS", "4"))

# Etsy through Apify
APIFY_ACTOR = os.environ.get("APIFY_ACTOR", "automation-lab~etsy-scraper")
APIFY_MAX_USD = float(os.environ.get("APIFY_MAX_USD", "3"))   # hard cap per run

# dollar rate for showing Etsy prices in toman (same as Caravan Sanat's rate)
USD_TOMAN = int(os.environ.get("USD_TOMAN", "270000"))

ETSY_QUERIES = ["necklace", "earrings", "ring", "bracelet", "anklet", "brooch", "pendant", "jewelry set"]
ETSY_PER_QUERY = int(os.environ.get("ETSY_PER_QUERY", "40"))

BASALAM_QUERIES = ["گردنبند", "گوشواره", "انگشتر", "دستبند", "پابند", "سنجاق سینه", "آویز گردنبند", "ست زیورآلات"]
BASALAM_PER_QUERY = int(os.environ.get("BASALAM_PER_QUERY", "60"))
BASALAM_DELAY = (4.0, 8.0)          # seconds between Basalam requests (slow on purpose)

TOP_N = int(os.environ.get("TOP_N", "200"))


def secret(name: str) -> str:
    return os.environ.get(name, "").strip()
