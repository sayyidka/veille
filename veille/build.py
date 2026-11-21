import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from . import db
from .scoring import Scorer, rank

log = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parent.parent


def select_items(conn, config: dict) -> list[dict]:
    s = config["settings"]
    scorer = Scorer(config)
    blocked = {x.lower() for x in config.get("exclude_sources", [])}
    out, seen_titles = [], set()
    for row in db.recent(conn, s["window_days"]):
        if (row["source"] or "").lower() in blocked:
            continue
        keep, topics, best, matched = scorer.score(
            row["title"], row["summary"] or "", row["min_score"], bool(row["skeptic"])
        )
        if not keep:
            continue
        # Same story syndicated in several places: keep the first one seen
        tkey = row["title"].strip().lower()
        if tkey in seen_titles:
            continue
        seen_titles.add(tkey)
        published = datetime.fromisoformat(row["published"])
        extra = json.loads(row["extra"] or "{}")
        out.append({
            "t": row["title"],
            "u": row["url"],
            "s": row["source"],
            "y": row["type"],
            "l": row["lang"],
            "p": published.isoformat(timespec="minutes"),
            "e": row["engagement"],
            "c": row["comments_url"],
            "n": row["num_comments"],
            "x": (row["summary"] or "")[:240],
            "k": matched,
            "o": topics,
            "r": rank(best, row["engagement"] or 0, published),
            **({"lk": extra["link"]} if extra.get("link") else {}),
        })
    out.sort(key=lambda i: i["r"], reverse=True)
    per_type, capped = {}, []
    for it in out:
        per_type[it["y"]] = per_type.get(it["y"], 0) + 1
        if per_type[it["y"]] <= s.get("max_per_type", 120):
            capped.append(it)
    return capped


def build(conn, config: dict, out_dir: Path = ROOT / "site") -> int:
    items = select_items(conn, config)
    payload = {
        "generated": datetime.now(timezone.utc).isoformat(timespec="minutes"),
        "topics": {k: t["label"] for k, t in config["topics"].items()},
        "items": items,
    }
    # Embed the data in the page so it also works when opened as a local file.
    data_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    env = Environment(loader=FileSystemLoader(ROOT / "templates"), autoescape=True)
    html = env.get_template("index.html.j2").render(data_json=data_json)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "index.html").write_text(html, encoding="utf-8")
    log.info("Built %s with %d items", out_dir / "index.html", len(items))
    return len(items)
