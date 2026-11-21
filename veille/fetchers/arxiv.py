import logging

import httpx

from ..models import Item
from . import clean_text, to_utc
from .rss import parse_entries

log = logging.getLogger(__name__)
API = "https://export.arxiv.org/api/query"


def fetch(config: dict, client: httpx.Client) -> list[Item]:
    cfg = config["sources"].get("arxiv") or {}
    cats = " OR ".join(f"cat:{c}" for c in cfg.get("categories", ["cs.CY"]))
    try:
        r = client.get(API, params={
            "search_query": cats,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
            "max_results": cfg.get("max_results", 150),
        })
        r.raise_for_status()
    except httpx.HTTPError as e:
        log.warning("arXiv failed: %s", e)
        return []
    items = []
    for e in parse_entries(r.content):
        url = e.get("link") or e.get("id")
        if not url:
            continue
        items.append(Item(
            url=url,
            title=clean_text(e.get("title"), 300),
            summary=clean_text(e.get("summary")),
            source="arXiv",
            type="study",
            published=to_utc(e.get("published_parsed") or e.get("published")),
        ))
    return items
