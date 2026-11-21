"""Reddit fetcher.

Uses OAuth (client-credentials, "script" app) when REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET
are set (needed from CI: Reddit blocks anonymous requests from datacenter IPs),
otherwise falls back to the public .json endpoints (fine from a home connection).
"""
import logging
import os
import time

import httpx

from ..models import Item
from . import clean_text, to_utc

log = logging.getLogger(__name__)


def _oauth_token(client: httpx.Client) -> str | None:
    cid, secret = os.environ.get("REDDIT_CLIENT_ID"), os.environ.get("REDDIT_CLIENT_SECRET")
    if not (cid and secret):
        return None
    r = client.post(
        "https://www.reddit.com/api/v1/access_token",
        data={"grant_type": "client_credentials"},
        auth=(cid, secret),
    )
    r.raise_for_status()
    return r.json()["access_token"]


def fetch(config: dict, client: httpx.Client) -> list[Item]:
    cfg = config["sources"].get("reddit") or {}
    t, limit = cfg.get("time", "week"), cfg.get("limit", 40)

    try:
        token = _oauth_token(client)
    except httpx.HTTPError as e:
        log.warning("Reddit OAuth failed, falling back to public API: %s", e)
        token = None
    if token:
        base, suffix = "https://oauth.reddit.com", ""
        headers = {"Authorization": f"Bearer {token}"}
        log.info("Reddit: using OAuth")
    elif cfg.get("public_fallback", False):
        base, suffix, headers = "https://www.reddit.com", ".json", {}
    else:
        log.info("Reddit: no API keys (REDDIT_CLIENT_ID/SECRET), skipping")
        return []

    requests = []
    for sub in cfg.get("subreddits", []):
        requests.append((sub, f"{base}/r/{sub['name']}/top{suffix}", {"t": t, "limit": limit}))
    for s in cfg.get("searches", []):
        requests.append((
            {"name": s["subreddit"], "lang": s.get("lang", "en")},
            f"{base}/r/{s['subreddit']}/search{suffix}",
            {"q": s["query"], "restrict_sr": 1, "sort": "top", "t": t, "limit": limit},
        ))

    items: list[Item] = []
    for sub, url, params in requests:
        try:
            r = client.get(url, params={**params, "raw_json": 1}, headers=headers)
            r.raise_for_status()
            children = r.json()["data"]["children"]
        except (httpx.HTTPError, KeyError, ValueError) as e:
            log.warning("Reddit r/%s failed: %s", sub["name"], e)
            continue
        for c in children:
            d = c["data"]
            if d.get("stickied") or d.get("over_18"):
                continue
            permalink = "https://www.reddit.com" + d["permalink"]
            summary = d.get("selftext") or ("" if d.get("is_self") else f"Link: {d.get('domain', '')}")
            items.append(Item(
                url=permalink,
                title=d["title"],
                summary=clean_text(summary),
                source=f"r/{d.get('subreddit', sub['name'])}",
                type="reddit",
                lang=sub.get("lang", "en"),
                published=to_utc(d.get("created_utc")),
                engagement=d.get("score") or 0,
                comments_url=permalink,
                num_comments=d.get("num_comments") or 0,
                min_score=sub.get("min_score"),
                skeptic=bool(sub.get("skeptic")),
                extra={"link": None if d.get("is_self") else d.get("url")},
            ))
        time.sleep(1 if token else 2)  # be polite with rate limits
    return items
