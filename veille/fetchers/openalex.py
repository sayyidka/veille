import logging
from datetime import date, timedelta

import httpx

from ..models import Item
from . import clean_text, to_utc

log = logging.getLogger(__name__)
API = "https://api.openalex.org/works"


def _abstract(inv: dict | None) -> str:
    """OpenAlex ships abstracts as an inverted index {word: [positions]}."""
    if not inv:
        return ""
    pos = {p: w for w, ps in inv.items() for p in ps}
    return " ".join(pos[i] for i in sorted(pos))


def fetch(config: dict, client: httpx.Client) -> list[Item]:
    cfg = config["sources"].get("openalex") or {}
    today = date.today()
    since = today - timedelta(days=cfg.get("days", 30))
    items: dict[str, Item] = {}
    for q in cfg.get("queries", []):
        try:
            r = client.get(API, params={
                "search": q,
                "filter": f"from_publication_date:{since},to_publication_date:{today},has_abstract:true,type:article",
                "sort": "publication_date:desc",
                "per-page": cfg.get("per_query", 15),
            })
            r.raise_for_status()
        except httpx.HTTPError as e:
            log.warning("OpenAlex %r failed: %s", q, e)
            continue
        for w in r.json().get("results", []):
            url = w.get("doi") or w.get("id")
            if not url or url in items or not w.get("title"):
                continue
            venue = ((w.get("primary_location") or {}).get("source") or {}).get("display_name")
            items[url] = Item(
                url=url,
                title=clean_text(w["title"], 300),
                summary=clean_text(_abstract(w.get("abstract_inverted_index"))),
                source=venue or "OpenAlex",
                type="study",
                lang=(w.get("language") or "en")[:2],
                published=to_utc(w.get("publication_date")),
                engagement=w.get("cited_by_count") or 0,
            )
    return list(items.values())
