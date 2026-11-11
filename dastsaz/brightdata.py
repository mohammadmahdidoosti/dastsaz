"""Bright Data's Instagram profile scraper: public profile numbers and recent posts, ~5,000 free records a month.
Needs BRIGHTDATA_API_KEY (entered by the owner in Coolify, never in the repo).
Returns profiles in the same shape as the Apify profile tool, so the rest of the code does not care which one ran.
"""
from __future__ import annotations

import logging
import time

import requests

from . import config as C

log = logging.getLogger(__name__)
API = "https://api.brightdata.com/datasets/v3"
PROFILES = "gd_l1vikfch901nx3by4"


def ready() -> bool:
    return bool(C.secret("BRIGHTDATA_API_KEY"))


def _h() -> dict:
    return {"Authorization": f"Bearer {C.secret('BRIGHTDATA_API_KEY')}", "Content-Type": "application/json"}


def to_profile(x: dict) -> dict:
    posts = []
    for p in x.get("posts") or []:
        posts.append({"caption": str(p.get("caption") or ""), "likesCount": p.get("likes"), "commentsCount": p.get("comments"),
                      "timestamp": p.get("datetime"), "displayUrl": p.get("image_url"), "mentions": []})
    return {"username": str(x.get("account") or "").lower(), "fullName": x.get("full_name") or x.get("profile_name") or "",
            "biography": x.get("biography") or "", "followersCount": x.get("followers"), "postsCount": x.get("posts_count"),
            "isBusinessAccount": bool(x.get("is_business_account")), "businessCategoryName": x.get("business_category_name") or "",
            "profilePicUrl": x.get("profile_image_link") or "", "latestPosts": posts, "via": "brightdata"}


def profiles(usernames: list[str], max_wait: int = 900, sess=None, sleep=time.sleep) -> tuple[list[dict], list[str]]:
    """(profiles found, handles that came back private, missing or with an error)."""
    users = [u.strip().lstrip("@").lower() for u in usernames if u and u.strip()]
    if not users:
        return [], []
    s = sess or requests.Session()
    r = s.post(f"{API}/trigger", params={"dataset_id": PROFILES, "include_errors": "true"}, headers=_h(), timeout=60,
               json=[{"url": f"https://www.instagram.com/{u}/"} for u in users])
    if r.status_code >= 400:
        raise RuntimeError(f"bright data trigger HTTP {r.status_code}: {r.text[:200]}")
    sid = r.json().get("snapshot_id")
    if not sid:
        raise RuntimeError(f"bright data: no snapshot id ({r.text[:200]})")
    waited = 0
    while True:
        st = s.get(f"{API}/progress/{sid}", headers=_h(), timeout=30).json().get("status")
        if st == "ready":
            break
        if st == "failed" or waited >= max_wait:
            raise RuntimeError(f"bright data snapshot {sid}: {st or 'timeout'}")
        sleep(10)
        waited += 10
    rows = s.get(f"{API}/snapshot/{sid}", params={"format": "json"}, headers=_h(), timeout=120).json()
    out, ok = [], set()
    for x in rows if isinstance(rows, list) else []:
        if x.get("error") or x.get("is_private") or not x.get("account"):
            continue
        p = to_profile(x)
        out.append(p)
        ok.add(p["username"])
    return out, [u for u in users if u not in ok]
