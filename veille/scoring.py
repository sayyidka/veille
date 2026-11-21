import math
import re
import unicodedata
from datetime import datetime, timezone


def fold(text: str) -> str:
    """Lowercase, strip accents, normalize apostrophes."""
    text = unicodedata.normalize("NFKD", text.lower().replace("’", "'"))
    return "".join(c for c in text if not unicodedata.combining(c))


def _pattern(phrase: str) -> re.Pattern:
    return re.compile(r"(?<![\w-])" + re.escape(fold(phrase)) + r"(?![\w-])")


class Scorer:
    def __init__(self, config: dict):
        self.threshold = config["settings"]["threshold"]
        self.labels = {k: t["label"] for k, t in config["topics"].items()}
        self.topics = {
            k: [(kw, _pattern(kw), w) for kw, w in t["keywords"].items()]
            for k, t in config["topics"].items()
        }
        self.exclude = [_pattern(p) for p in config.get("exclude", [])]
        self.skeptic_topic = config["settings"].get("skeptic_topic", "hype_fomo")

    def score(self, title: str, summary: str, min_score=None, skeptic=False):
        """Return (keep, topics, best_score, matched_keywords)."""
        text = fold(f"{title} \n {summary}")
        if any(p.search(text) for p in self.exclude):
            return False, [], 0, []
        scores, matched = {}, []
        for topic, kws in self.topics.items():
            s = 0
            for kw, pat, w in kws:
                if pat.search(text):
                    s += w
                    matched.append(kw)
            scores[topic] = s
        best = max(scores.values(), default=0)
        threshold = self.threshold if min_score is None else min_score
        keep = best >= threshold or (threshold <= 0)
        topics = [t for t, s in scores.items() if s >= self.threshold]
        if not topics and best > 0:
            topics = [t for t, s in scores.items() if s == best]
        if skeptic and self.skeptic_topic not in topics:
            topics.append(self.skeptic_topic)
        # Show the most specific (longest) keywords first
        matched = sorted(set(matched), key=lambda k: -len(k))[:5]
        return keep, topics, best, matched


def rank(best: float, engagement: int, published: datetime) -> float:
    age_days = (datetime.now(timezone.utc) - published).total_seconds() / 86400
    return round(min(best, 8) + 0.7 * math.log1p(max(engagement, 0)) + 3 * math.exp(-age_days / 5), 3)
