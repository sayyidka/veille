import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .models import Item

SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    url TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    summary TEXT,
    source TEXT,
    type TEXT,
    lang TEXT,
    published TEXT,
    engagement INTEGER DEFAULT 0,
    comments_url TEXT,
    num_comments INTEGER DEFAULT 0,
    min_score REAL,
    skeptic INTEGER DEFAULT 0,
    extra TEXT,
    first_seen TEXT
);
CREATE INDEX IF NOT EXISTS idx_items_published ON items(published);
"""

_TRACKING = ("utm_", "fbclid", "gclid", "ref", "ref_src", "smid", "cmpid")


def normalize_url(url: str) -> str:
    """Drop tracking params, fragment and trailing slash so the same page dedups."""
    try:
        p = urlsplit(url.strip())
    except ValueError:
        return url
    query = urlencode([(k, v) for k, v in parse_qsl(p.query) if not k.lower().startswith(_TRACKING)])
    path = p.path.rstrip("/") or "/"
    return urlunsplit((p.scheme.lower(), p.netloc.lower().removeprefix("www."), path, query, ""))


def connect(path: str | Path) -> sqlite3.Connection:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def upsert(conn: sqlite3.Connection, items: list[Item]) -> int:
    """Insert new items; refresh engagement counters on existing ones. Returns # new."""
    now = datetime.now(timezone.utc).isoformat()
    before = conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]
    conn.executemany(
        """
        INSERT INTO items (url, title, summary, source, type, lang, published, engagement,
                           comments_url, num_comments, min_score, skeptic, extra, first_seen)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(url) DO UPDATE SET
            engagement = MAX(items.engagement, excluded.engagement),
            num_comments = MAX(items.num_comments, excluded.num_comments),
            min_score = excluded.min_score,
            skeptic = excluded.skeptic
        """,
        [
            (
                normalize_url(i.url), i.title, i.summary, i.source, i.type, i.lang,
                i.published.isoformat(), i.engagement, i.comments_url, i.num_comments,
                i.min_score, int(i.skeptic), json.dumps(i.extra), now,
            )
            for i in items
        ],
    )
    conn.commit()
    return conn.execute("SELECT COUNT(*) FROM items").fetchone()[0] - before


def recent(conn: sqlite3.Connection, days: int) -> list[sqlite3.Row]:
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    return conn.execute("SELECT * FROM items WHERE published >= ?", (since,)).fetchall()


def prune(conn: sqlite3.Connection, days: int) -> None:
    """Keep the DB small: drop anything well outside the display window."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days * 2)).isoformat()
    conn.execute("DELETE FROM items WHERE published < ?", (cutoff,))
    conn.commit()
