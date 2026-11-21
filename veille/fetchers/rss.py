import logging

import feedparser
import httpx

from ..models import Item
from . import clean_text, to_utc

log = logging.getLogger(__name__)


def parse_entries(feed_bytes: bytes):
    return feedparser.parse(feed_bytes).entries


def entry_date(e):
    return e.get("published_parsed") or e.get("updated_parsed") or e.get("published") or e.get("updated")


def fetch(config: dict, client: httpx.Client) -> list[Item]:
    items: list[Item] = []
    for src in config["sources"].get("rss") or []:
        try:
            r = client.get(src["url"])
            r.raise_for_status()
            entries = parse_entries(r.content)
        except httpx.HTTPError as e:
            log.warning("RSS %s failed: %s", src["name"], e)
            continue
        if not entries:
            log.warning("RSS %s returned no entries", src["name"])
        for e in entries:
            # Podcast feeds sometimes have no web page per episode: use the audio file
            link = e.get("link") or next((x.get("href") for x in e.get("enclosures", []) if x.get("href")), None)
            if not link or not e.get("title"):
                continue
            summary = e.get("summary") or (e.get("content") or [{}])[0].get("value", "")
            items.append(Item(
                url=link,
                title=clean_text(e["title"], 300),
                summary=clean_text(summary),
                source=src["name"],
                type=src.get("type", "article"),
                lang=src.get("lang", "en"),
                published=to_utc(entry_date(e)),
                min_score=src.get("min_score"),
                skeptic=bool(src.get("skeptic")),
            ))
    return items
