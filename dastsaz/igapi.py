"""Instagram's own official API (Graph API "Business Discovery"): free public data about other Business and
Creator accounts, read through our own Instagram professional account. Needs IG_GRAPH_TOKEN and IG_USER_ID
(entered by the owner, never in the repo). Personal accounts are not visible this way; those are skipped.
Returns profiles in the same shape as the Apify profile tool, so the rest of the code does not care which one ran.
Instagram allows about 200 calls an hour for one account; we stay well under that.
"""
from __future__ import annotations

import logging
import time

import requests

from . import config as C

log = logging.getLogger(__name__)
VERSION = C.secret("IG_GRAPH_VERSION") or "v25.0"
FIELDS = ("username,name,biography,followers_count,media_count,"
          "media.limit(12){caption,like_count,comments_count,timestamp,media_url,media_type,thumbnail_url}")


def ready() -> bool:
    return bool(C.secret("IG_GRAPH_TOKEN") and C.secret("IG_USER_ID"))


def to_profile(bd: dict) -> dict:
    posts = []
    for m in ((bd.get("media") or {}).get("data") or []):
        cap = str(m.get("caption") or "")
        posts.append({"caption": cap, "likesCount": m.get("like_count"), "commentsCount": m.get("comments_count"),
                      "timestamp": m.get("timestamp"),
                      "displayUrl": m.get("thumbnail_url") if m.get("media_type") == "VIDEO" else m.get("media_url"),
                      "mentions": []})
    return {"username": bd.get("username"), "fullName": bd.get("name"), "biography": bd.get("biography"),
            "followersCount": bd.get("followers_count"), "postsCount": bd.get("media_count"),
            "latestPosts": posts, "via": "graph"}


def profile(username: str, sess=None) -> dict | None:
    """None if the account is personal, private or missing."""
    sess = sess or requests.Session()
    r = sess.get(f"https://graph.facebook.com/{VERSION}/{C.secret('IG_USER_ID')}", timeout=30, params={
        "fields": f"business_discovery.username({username}){{{FIELDS}}}", "access_token": C.secret("IG_GRAPH_TOKEN")})
    j = r.json()
    if "business_discovery" in j:
        return to_profile(j["business_discovery"])
    err = (j.get("error") or {})
    if err.get("code") in (4, 17, 32, 613):                     # rate limit: stop for now
        raise RuntimeError("instagram rate limit")
    if err.get("code") == 190:
        raise RuntimeError("instagram token expired")
    return None


def profiles(usernames: list[str], max_calls: int = 150, pause: float = 1.0, sess=None, sleep=time.sleep) -> tuple[list[dict], list[str]]:
    """(profiles found, handles that are not readable this way)."""
    sess = sess or requests.Session()
    out, skipped = [], []
    for u in usernames[:max_calls]:
        try:
            p = profile(u, sess)
        except RuntimeError as e:
            log.warning("instagram api: %s", e)
            break
        except requests.RequestException as e:
            log.info("instagram api %s: %s", u, e)
            continue
        (out.append(p) if p else skipped.append(u))
        sleep(pause)
    return out, skipped
