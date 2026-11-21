import html
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import httpx

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def make_client(config: dict) -> httpx.Client:
    s = config["settings"]
    return httpx.Client(
        headers={"User-Agent": s["user_agent"]},
        timeout=s.get("timeout", 20),
        follow_redirects=True,
    )


def clean_text(raw: str | None, limit: int = 400) -> str:
    """Strip HTML tags/entities, collapse whitespace, truncate."""
    if not raw:
        return ""
    text = _WS_RE.sub(" ", html.unescape(_TAG_RE.sub(" ", raw))).strip()
    if len(text) > limit:
        text = text[:limit].rsplit(" ", 1)[0] + "…"
    return text


def to_utc(value) -> datetime:
    """Parse common date representations into an aware UTC datetime (now if unknown)."""
    now = datetime.now(timezone.utc)
    if value is None:
        return now
    try:
        if isinstance(value, (int, float)):
            dt = datetime.fromtimestamp(value, timezone.utc)
        elif isinstance(value, datetime):
            dt = value
        elif hasattr(value, "tm_year"):  # time.struct_time from feedparser
            dt = datetime(*value[:6], tzinfo=timezone.utc)
        else:
            s = str(value).strip()
            try:
                dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
            except ValueError:
                dt = parsedate_to_datetime(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        dt = dt.astimezone(timezone.utc)
        return min(dt, now)  # some feeds/APIs report future dates
    except Exception:
        return now
