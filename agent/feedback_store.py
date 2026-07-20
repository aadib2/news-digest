"""
feedback_store.py
Persists user reactions (👍 👎 🔖) to SQLite and provides
a simple summary for the curator to learn from.
"""

import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Set
from collections import Counter
from contextlib import contextmanager

# Support both DATABASE_PATH (new) and FEEDBACK_DB_PATH (legacy) env vars
_raw_db_path = os.getenv("DATABASE_PATH") or os.getenv("FEEDBACK_DB_PATH", "./data/feedback.db")
DATABASE_PATH = Path(_raw_db_path).expanduser()
DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)

# Default structure for backward compatibility
_DEFAULT = {
    "upvoted": [],
    "downvoted": [],
    "saved": [],
    "message_article_map": {},
    "upvoted_count": 0,
    "downvoted_count": 0,
    "saved_count": 0,
}


def _connect() -> sqlite3.Connection:
    """Create a new connection with WAL mode and busy timeout."""
    conn = sqlite3.connect(str(DATABASE_PATH), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=5000;")
    return conn


@contextmanager
def _db():
    """Short-lived connection with row_factory and automatic commit/close."""
    conn = _connect()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _ensure_schema():
    """Create tables and parent directory if missing."""
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS articles (
                message_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                url TEXT,
                source TEXT,
                category TEXT,
                relevance_score INTEGER,
                sent_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS reactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id TEXT NOT NULL REFERENCES articles(message_id),
                emoji TEXT NOT NULL CHECK(emoji IN ('👍','👎','🔖')),
                reacted_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_reactions_message_id ON reactions(message_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_articles_url ON articles(url)
        """)


# Initialize schema on module load
_ensure_schema()


def register_message(message_id: int, article: Dict):
    """Map a Discord message ID to the article it represents."""
    with _db() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO articles (message_id, title, url, source, category, relevance_score)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                str(message_id),
                article.get("title", ""),
                article.get("url", ""),
                article.get("source", ""),
                article.get("category", ""),
                article.get("relevance_score", 0),
            ),
        )


def record_reaction(message_id: int, emoji: str):
    """Record a user reaction for a given message."""
    if emoji not in ("👍", "👎", "🔖"):
        return
    with _db() as conn:
        conn.execute(
            "INSERT INTO reactions (message_id, emoji) VALUES (?, ?)",
            (str(message_id), emoji),
        )


def get_summary() -> Dict:
    """Return a summary the curator can use to adjust rankings."""
    with _db() as conn:
        # Total reaction counts
        upvoted_count = conn.execute(
            "SELECT COUNT(*) FROM reactions WHERE emoji = '👍'"
        ).fetchone()[0]
        downvoted_count = conn.execute(
            "SELECT COUNT(*) FROM reactions WHERE emoji = '👎'"
        ).fetchone()[0]
        saved_count = conn.execute(
            "SELECT COUNT(*) FROM reactions WHERE emoji = '🔖'"
        ).fetchone()[0]

        # Top topics (categories) from upvoted + saved
        engaged_rows = conn.execute("""
            SELECT a.category, COUNT(*) as cnt
            FROM reactions r
            JOIN articles a ON r.message_id = a.message_id
            WHERE r.emoji IN ('👍', '🔖') AND a.category != ''
            GROUP BY a.category
            ORDER BY cnt DESC
            LIMIT 3
        """).fetchall()
        top_topics = [row["category"] for row in engaged_rows]

        # Top sources from upvoted + saved
        source_rows = conn.execute("""
            SELECT a.source, COUNT(*) as cnt
            FROM reactions r
            JOIN articles a ON r.message_id = a.message_id
            WHERE r.emoji IN ('👍', '🔖') AND a.source != ''
            GROUP BY a.source
            ORDER BY cnt DESC
            LIMIT 3
        """).fetchall()
        top_sources = [row["source"] for row in source_rows]

        total_reactions = upvoted_count + downvoted_count
        engagement_rate = (
            upvoted_count / total_reactions if total_reactions > 0 else 0
        )

    return {
        "upvoted_count": upvoted_count,
        "downvoted_count": downvoted_count,
        "saved_count": saved_count,
        "engagement_rate": round(engagement_rate, 2),
        "top_topics": top_topics,
        "top_sources": top_sources,
    }


def get_saved_articles() -> List[Dict]:
    """Return all saved (🔖) articles."""
    with _db() as conn:
        rows = conn.execute("""
            SELECT a.title, a.url, a.source, a.category, a.relevance_score, r.reacted_at
            FROM reactions r
            JOIN articles a ON r.message_id = a.message_id
            WHERE r.emoji = '🔖'
            ORDER BY r.reacted_at DESC
        """).fetchall()

    return [
        {
            "title": row["title"],
            "url": row["url"],
            "source": row["source"],
            "category": row["category"],
            "relevance_score": row["relevance_score"],
            "timestamp": row["reacted_at"],
        }
        for row in rows
    ]


def get_sent_urls() -> Set[str]:
    """Return a set of all article URLs that have been sent (for deduplication)."""
    with _db() as conn:
        rows = conn.execute("SELECT DISTINCT url FROM articles WHERE url != ''").fetchall()
    return {row["url"] for row in rows}