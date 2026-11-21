"""Items fetched on a home computer by `veille relay` and committed to relay/local_items.json.

Used for feeds that block cloud servers (Substack's Cloudflare challenge on *.substack.com).
"""
import json
import logging
from datetime import datetime
from pathlib import Path

import httpx

from ..models import Item

log = logging.getLogger(__name__)
RELAY_FILE = Path(__file__).resolve().parent.parent.parent / "relay" / "local_items.json"


def save(items: list[Item], path: Path = RELAY_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for i in sorted(items, key=lambda i: (i.published, i.url), reverse=True):
        d = {k: v for k, v in i.__dict__.items() if v is not None}  # keep 0: min_score 0 = always keep
        d["published"] = i.published.isoformat()
        rows.append(d)
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def fetch(config: dict, client: httpx.Client) -> list[Item]:
    if not RELAY_FILE.exists():
        log.info("Relay: %s not found (run `veille relay` on your computer)", RELAY_FILE.name)
        return []
    items = []
    for d in json.loads(RELAY_FILE.read_text(encoding="utf-8")):
        d["published"] = datetime.fromisoformat(d["published"])
        items.append(Item(**d))
    return items
