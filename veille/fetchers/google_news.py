import logging

import httpx

from ..models import Item
from . import clean_text, to_utc
from .rss import entry_date, parse_entries

log = logging.getLogger(__name__)
BASE = "https://news.google.com/rss/search"


def fetch(config: dict, client: httpx.Client) -> list[Item]:
    cfg = config["sources"].get("google_news") or {}
    editions = cfg.get("editions", {})
    items: dict[str, Item] = {}
    for lang, queries in (cfg.get("queries") or {}).items():
        ed = editions[lang]
        for q in queries:
            try:
                r = client.get(BASE, params={"q": f"{q} when:7d", **ed})
                r.raise_for_status()
            except httpx.HTTPError as e:
                log.warning("Google News %r failed: %s", q, e)
                continue
            for e in parse_entries(r.content):
                if not e.get("link") or e["link"] in items:
                    continue
                outlet = (e.get("source") or {}).get("title") or "Google News"
                title = e.get("title", "")
                suffix = f" - {outlet}"
                if title.endswith(suffix):
                    title = title[: -len(suffix)]
                items[e["link"]] = Item(
                    url=e["link"],
                    title=clean_text(title, 300),
                    source=outlet,
                    type="news",
                    lang=lang,
                    published=to_utc(entry_date(e)),
                    min_score=cfg.get("min_score"),
                )
    return list(items.values())
