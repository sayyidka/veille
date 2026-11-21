from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Item:
    url: str
    title: str
    source: str  # human-readable, e.g. "r/nosurf", "Hacker News", "The Atlantic"
    type: str  # news | reddit | hn | article | study
    published: datetime  # timezone-aware UTC
    summary: str = ""
    lang: str = "en"
    engagement: int = 0  # HN points / Reddit upvotes / citations
    comments_url: str | None = None
    num_comments: int = 0
    # Per-source options carried to scoring
    min_score: float | None = None  # override global threshold (0 = always keep)
    skeptic: bool = False  # source belongs to the "AI skepticism" tab
    extra: dict = field(default_factory=dict)
