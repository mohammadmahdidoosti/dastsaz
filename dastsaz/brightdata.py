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
POSTS = "gd_lk5ns7kz21pck8jpis"          # the profile rows carry no like counts; these do
PER = 6                                          # recent posts read per page: 1 + 6 records a page


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


def raw(users: list[str], max_wait: int = 900, sess=None, sleep=time.sleep) -> list[dict]:
    """Bright Data's own rows for these handles."""
    return _collect(PROFILES, [f"https://www.instagram.com/{u}/" for u in users], max_wait, sess, sleep)


def _key(url: str) -> str:
    return str(url or "").split("?")[0].rstrip("/").lower()


def _collect(dataset: str, urls: list[str], max_wait: int = 900, sess=None, sleep=time.sleep) -> list[dict]:
    if not urls:
        return []
    s = sess or requests.Session()
    r = s.post(f"{API}/trigger", params={"dataset_id": dataset, "include_errors": "true"}, headers=_h(), timeout=60,
               json=[{"url": u} for u in urls])
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
    return rows if isinstance(rows, list) else []


def profiles(usernames: list[str], max_wait: int = 900, sess=None, sleep=time.sleep) -> tuple[list[dict], list[str]]:
    """(profiles found, handles that came back private, missing or with an error)."""
    users = [u.strip().lstrip("@").lower() for u in usernames if u and u.strip()]
    if not users:
        return [], []
    rows = [x for x in raw(users, max_wait=max_wait, sess=sess, sleep=sleep)
            if not x.get("error") and not x.get("is_private") and x.get("account")]
    want = [q["url"] for x in rows for q in [p for p in (x.get("posts") or []) if p.get("url") and not p.get("is_pinned")][:PER]]
    counts = {}
    try:
        for q in _collect(POSTS, want, max_wait, sess, sleep):
            if not q.get("error") and q.get("likes") is not None:
                counts[_key(q.get("url"))] = (q.get("likes"), q.get("num_comments") or 0)
    except RuntimeError as e:                                   # profiles still count without the like numbers
        log.warning("bright data posts: %s", e)
    out, ok = [], set()
    for x in rows:
        p = to_profile(x)
        posts = []
        for q, src in zip(p["latestPosts"], x.get("posts") or []):
            c = counts.get(_key(src.get("url")))
            if c:
                q["likesCount"], q["commentsCount"] = c
                posts.append(q)
        p["latestPosts"] = posts or p["latestPosts"]
        out.append(p)
        ok.add(p["username"])
    return out, [u for u in users if u not in ok]
