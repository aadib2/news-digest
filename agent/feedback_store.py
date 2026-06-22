"""
feedback_store.py
Persists user reactions (👍 👎 🔖) to disk and provides
a simple summary for the curator to learn from.
"""

import json
import os
from datetime import datetime
from typing import Dict, List
from collections import Counter


FEEDBACK_FILE = os.getenv("FEEDBACK_PATH", "/data/feedback.json")

_DEFAULT = {
    "upvoted": [],
    "downvoted": [],
    "saved": [],
    "message_article_map": {},   # message_id (str) → article dict
    "upvoted_count": 0,
    "downvoted_count": 0,
    "saved_count": 0,
}


def _load() -> Dict:
    if os.path.exists(FEEDBACK_FILE):
        with open(FEEDBACK_FILE) as f:
            return json.load(f)
    return _DEFAULT.copy()


def _save(data: Dict):
    with open(FEEDBACK_FILE, "w") as f:
        json.dump(data, f, indent=2)


def register_message(message_id: int, article: Dict):
    """Map a Discord message ID to the article it represents."""
    data = _load()
    data["message_article_map"][str(message_id)] = {
        "title": article.get("title", ""),
        "url": article.get("url", ""),
        "source": article.get("source", ""),
        "category": article.get("category", ""),
        "relevance_score": article.get("relevance_score", 0),
    }
    _save(data)


def record_reaction(message_id: int, emoji: str):
    """Record a user reaction for a given message."""
    data = _load()
    article = data["message_article_map"].get(str(message_id)) # fetch article info for given message

    entry = {
        "message_id": str(message_id),
        "title": article["title"] if article else "Unknown",
        "url": article["url"] if article else "",
        "category": article["category"] if article else "",
        "source": article["source"] if article else "",
        "timestamp": datetime.now().isoformat(),
    }

    if emoji == "👍":
        data["upvoted"].append(entry)
        data["upvoted_count"] += 1
    elif emoji == "👎":
        data["downvoted"].append(entry)
        data["downvoted_count"] += 1
    elif emoji == "🔖":
        data["saved"].append(entry)
        data["saved_count"] += 1

    _save(data)


def get_summary() -> Dict:
    """Return a summary the curator can use to adjust rankings."""
    data = _load()

    # Determine most engaged categories from upvotes + saves
    engaged = data["upvoted"] + data["saved"]
    category_counts = Counter(e.get("category", "") for e in engaged if e.get("category"))
    top_topics = [cat for cat, _ in category_counts.most_common(3)]

    # Determine most engaged sources
    source_counts = Counter(e.get("source", "") for e in engaged if e.get("source"))
    top_sources = [src for src, _ in source_counts.most_common(3)]

    total_reactions = data["upvoted_count"] + data["downvoted_count"]
    engagement_rate = (
        data["upvoted_count"] / total_reactions if total_reactions > 0 else 0
    )

    return {
        "upvoted_count": data["upvoted_count"],
        "downvoted_count": data["downvoted_count"],
        "saved_count": data["saved_count"],
        "engagement_rate": round(engagement_rate, 2),
        "top_topics": top_topics,
        "top_sources": top_sources,
    }


def get_saved_articles() -> List[Dict]:
    """Return all saved (🔖) articles."""
    data = _load()
    return data.get("saved", [])
