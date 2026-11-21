import logging
import os

import feedparser
import httpx

from ..models import Item
from . import clean_text, to_utc

log = logging.getLogger(__name__)


def parse_entries(feed_bytes: bytes):
    return feedparser.parse(feed_bytes).entries


def entry_date(e):
    return e.get("published_parsed") or e.get("updated_parsed") or e.get("published") or e.get("updated")


def in_ci() -> bool:
    return os.environ.get("GITHUB_ACTIONS") == "true"


def fetch(config: dict, client: httpx.Client, local_only: bool = False) -> list[Item]:
    """Fetch RSS sources.

    Feeds marked `local: true` (Substack blocks cloud servers) are skipped in CI: they are
    fetched from a home connection by `veille relay` and reach CI via relay/local_items.json.
    """
    feeds = config["sources"].get("rss") or []
    if local_only:
        feeds = [f for f in feeds if f.get("local")]
    elif in_ci():
        feeds = [f for f in feeds if not f.get("local")]
    return fetch_feeds(feeds, client)


def fetch_feeds(feeds: list[dict], client: httpx.Client) -> list[Item]:
    items: list[Item] = []
    for src in feeds:
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
