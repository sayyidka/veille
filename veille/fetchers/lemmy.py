"""Lemmy (open, federated Reddit alternative). Public API, no key needed."""
import logging
import time

import httpx

from ..models import Item
from . import clean_text, to_utc

log = logging.getLogger(__name__)


def fetch(config: dict, client: httpx.Client) -> list[Item]:
    cfg = config["sources"].get("lemmy") or {}
    items: list[Item] = []
    for com in cfg.get("communities", []):
        inst, name = com["instance"], com["name"]
        try:
            r = client.get(f"https://{inst}/api/v3/post/list", params={
                "community_name": name, "sort": cfg.get("sort", "TopWeek"), "limit": cfg.get("limit", 30),
            })
            r.raise_for_status()
            posts = r.json().get("posts", [])
        except (httpx.HTTPError, ValueError) as e:
            log.warning("Lemmy %s@%s failed: %s", name, inst, e)
            continue
        for p in posts:
            post, counts = p["post"], p.get("counts", {})
            if post.get("nsfw") or post.get("removed") or post.get("deleted"):
                continue
            if (counts.get("score") or 0) < com.get("min_votes", cfg.get("min_votes", 10)):
                continue
            thread = f"https://{inst}/post/{post['id']}"
            link = post.get("url")
            items.append(Item(
                url=post.get("ap_id") or thread,
                title=clean_text(post["name"], 300),
                summary=clean_text(post.get("body") or post.get("embed_description") or ""),
                source=f"{name}@{inst.split('.')[0] if inst != 'lemmy.world' else 'lemmy'}",
                type="forum",
                lang=com.get("lang", "en"),
                published=to_utc(post.get("published")),
                engagement=counts.get("score") or 0,
                comments_url=thread,
                num_comments=counts.get("comments") or 0,
                min_score=com.get("min_score"),
                skeptic=bool(com.get("skeptic")),
                extra={"link": link if link and not link.startswith(f"https://{inst}/pictrs") else None},
            ))
        time.sleep(0.5)
    return items
