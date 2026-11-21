"""Bluesky public search (no key). Only keeps posts sharing an external link:
raw posts are too noisy, but "article + what people say about it" is great material."""
import logging
from datetime import datetime, timedelta, timezone

import httpx

from ..models import Item
from . import clean_text, to_utc

log = logging.getLogger(__name__)
API = "https://api.bsky.app/xrpc/app.bsky.feed.searchPosts"


def _external(post: dict) -> dict | None:
    emb = post.get("embed") or {}
    if emb.get("$type") == "app.bsky.embed.recordWithMedia#view":
        emb = emb.get("media") or {}
    if emb.get("$type") == "app.bsky.embed.external#view":
        return emb.get("external")
    return None


def fetch(config: dict, client: httpx.Client) -> list[Item]:
    cfg = config["sources"].get("bluesky") or {}
    since = (datetime.now(timezone.utc) - timedelta(days=cfg.get("days", 7))).strftime("%Y-%m-%dT%H:%M:%SZ")
    min_likes = cfg.get("min_likes", 30)
    items: dict[str, Item] = {}
    for lang, queries in (cfg.get("queries") or {}).items():
        for q in queries:
            try:
                r = client.get(API, params={"q": q, "sort": "top", "since": since, "lang": lang, "limit": 50})
                r.raise_for_status()
                posts = r.json().get("posts", [])
            except (httpx.HTTPError, ValueError) as e:
                log.warning("Bluesky %r failed: %s", q, e)
                continue
            for p in posts:
                ext = _external(p)
                likes = p.get("likeCount") or 0
                if not ext or not ext.get("uri") or likes < min_likes:
                    continue
                handle = p["author"]["handle"]
                rkey = p["uri"].rsplit("/", 1)[-1]
                post_url = f"https://bsky.app/profile/{handle}/post/{rkey}"
                key = ext["uri"]  # same article shared by several people: keep the most liked
                if key in items and items[key].engagement >= likes:
                    continue
                text = clean_text(p["record"].get("text", ""), 300)
                items[key] = Item(
                    url=post_url,
                    title=clean_text(ext.get("title") or text, 300),
                    summary=f"@{handle}: {text}" + (f" | {clean_text(ext.get('description'), 200)}" if ext.get("description") else ""),
                    source="Bluesky",
                    type="social",
                    lang=lang,
                    published=to_utc(p["record"].get("createdAt") or p.get("indexedAt")),
                    engagement=likes,
                    comments_url=post_url,
                    num_comments=p.get("replyCount") or 0,
                    extra={"link": ext["uri"]},
                )
    return list(items.values())
