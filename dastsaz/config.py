"""Settings. Secrets come only from environment variables (entered by the owner in Coolify)."""
from __future__ import annotations

import os
from pathlib import Path

DATA_DIR = Path(os.environ.get("DATA_DIR", Path(__file__).resolve().parent.parent / "data")).resolve()

# Caravan Sanat crawler: we only READ its public status, never touch it
CARAVAN_STATUS_URL = os.environ.get("CARAVAN_STATUS_URL", "https://crawler.caravansanat.com/api/status")

# Waiting for the Caravan crawler / quiet night hours: OFF by default (owner's decision 2026-11-01:
# speed first, Dastsaz is light and crawls other sites). Turn on with GUARD=1 if ever needed.
GUARD = os.environ.get("GUARD", "0") == "1"
QUIET_FROM = int(os.environ.get("QUIET_FROM", "0"))     # used only when GUARD=1
QUIET_TO = int(os.environ.get("QUIET_TO", "0"))         # equal hours = no quiet time
TIMEZONE = "Asia/Tehran"

# AI through OpenRouter (same service the Caravan crawler uses)
AI_MODEL = os.environ.get("AI_MODEL", "deepseek/deepseek-v4.1-flash")
AI_WORKERS = int(os.environ.get("AI_WORKERS", "4"))

# the executive analysis (one call per report); a stronger model can be set here
ANALYST_MODEL = os.environ.get("ANALYST_MODEL", AI_MODEL)
# share of the shelf price paid to the maker at most (rule of thumb shown in the report)
BUY_SHARE = float(os.environ.get("BUY_SHARE", "0.45"))

# Etsy through Apify
APIFY_ACTOR = os.environ.get("APIFY_ACTOR", "automation-lab~etsy-scraper")
APIFY_MAX_USD = float(os.environ.get("APIFY_MAX_USD", "3"))   # hard cap per run

# dollar rate for showing Etsy prices in toman (same as Caravan Sanat's rate)
USD_TOMAN = int(os.environ.get("USD_TOMAN", "270000"))

ETSY_QUERIES = ["necklace", "earrings", "ring", "bracelet", "anklet", "brooch", "pendant", "jewelry set"]
ETSY_PER_QUERY = int(os.environ.get("ETSY_PER_QUERY", "50"))
# listing-page details (bought in 24h, in carts, tags): slow and came back "unavailable" in the first run
ETSY_ENRICH = os.environ.get("ETSY_ENRICH", "0") == "1"

BASALAM_QUERIES = ["گردنبند", "گوشواره", "انگشتر", "دستبند", "پابند", "سنجاق سینه", "آویز گردنبند", "ست زیورآلات"]
BASALAM_PER_QUERY = int(os.environ.get("BASALAM_PER_QUERY", "60"))
BASALAM_DELAY = (4.0, 8.0)          # seconds between Basalam requests (slow on purpose)

DIGIKALA = os.environ.get("DIGIKALA", "1") == "1"
DIGIKALA_PER_QUERY = int(os.environ.get("DIGIKALA_PER_QUERY", "40"))

TRENDS = os.environ.get("TRENDS", "1") == "1"
TRENDS_MAX_USD = float(os.environ.get("TRENDS_MAX_USD", "0.3"))

TOP_N = int(os.environ.get("TOP_N", "200"))


def secret(name: str) -> str:
    return os.environ.get(name, "").strip()


def today():
    """Today in Tehran (the server runs on UTC, so 2 a.m. Tehran would still be yesterday)."""
    import datetime as _dt
    from zoneinfo import ZoneInfo
    return _dt.datetime.now(ZoneInfo("Asia/Tehran")).date()
