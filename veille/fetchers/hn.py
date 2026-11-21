import logging
import time

import httpx

from ..models import Item
from . import clean_text, to_utc

log = logging.getLogger(__name__)
API = "https://hn.algolia.com/api/v1/search_by_date"


def fetch(config: dict, client: httpx.Client) -> list[Item]:
    cfg = config["sources"].get("hn") or {}
    since = int(time.time()) - config["settings"]["window_days"] * 86400
    items: dict[str, Item] = {}
    for q in cfg.get("queries", []):
        try:
            r = client.get(API, params={
                "query": q,
                "tags": "story",
                "numericFilters": f"points>{cfg.get('min_points', 15)},created_at_i>{since}",
                "hitsPerPage": 30,
            })
            r.raise_for_status()
        except httpx.HTTPError as e:
            log.warning("HN query %r failed: %s", q, e)
            continue
        for h in r.json().get("hits", []):
            hn_url = f"https://news.ycombinator.com/item?id={h['objectID']}"
            url = h.get("url") or hn_url
            if url in items or not h.get("title"):
                continue
            items[url] = Item(
                url=url,
                title=h["title"],
                summary=clean_text(h.get("story_text")),
                source="Hacker News",
                type="hn",
                published=to_utc(h.get("created_at_i")),
                engagement=h.get("points") or 0,
                comments_url=hn_url,
                num_comments=h.get("num_comments") or 0,
                min_score=cfg.get("min_score"),
            )
    return list(items.values())
