"""
test_feedback_store.py
Unit tests for the SQLite-backed feedback store.
Run: python -m test.test_feedback_store
"""

import os
import tempfile
from pathlib import Path

# Set test DB path BEFORE importing feedback_store
TEST_DB = Path(tempfile.gettempdir()) / "test_feedback.db"
os.environ["DATABASE_PATH"] = str(TEST_DB)

# Now import
import agent.feedback_store as feedback_store


def setup_module():
    """Clean up test DB tables before all tests."""
    import sqlite3
    with sqlite3.connect(TEST_DB) as conn:
        conn.execute("DELETE FROM reactions")
        conn.execute("DELETE FROM articles")
        conn.commit()


def teardown_module():
    """Clean up test DB after all tests."""
    if TEST_DB.exists():
        TEST_DB.unlink()


def test_register_and_summary():
    """Test registering a message and getting summary."""
    # Clear any existing data
    import sqlite3
    with sqlite3.connect(TEST_DB) as conn:
        conn.execute("DELETE FROM reactions")
        conn.execute("DELETE FROM articles")
        conn.commit()

    article = {
        "title": "Test Article",
        "url": "https://example.com/article",
        "source": "Test Source",
        "category": "machine_learning / AI",
        "relevance_score": 85,
    }
    msg_id = 123456789

    # Register message
    feedback_store.register_message(msg_id, article)

    # Record reactions
    feedback_store.record_reaction(msg_id, "👍")
    feedback_store.record_reaction(msg_id, "👎")
    feedback_store.record_reaction(msg_id, "🔖")

    # Get summary
    summary = feedback_store.get_summary()

    assert summary["upvoted_count"] == 1
    assert summary["downvoted_count"] == 1
    assert summary["saved_count"] == 1
    assert summary["top_topics"] == ["machine_learning / AI"]
    assert summary["top_sources"] == ["Test Source"]
    assert 0 <= summary["engagement_rate"] <= 1

    # Get saved articles
    saved = feedback_store.get_saved_articles()
    assert len(saved) == 1
    assert saved[0]["title"] == "Test Article"

    # Get sent URLs
    sent = feedback_store.get_sent_urls()
    assert "https://example.com/article" in sent

    print("✅ test_register_and_summary passed")


def test_multiple_articles():
    """Test with multiple articles and reactions."""
    import sqlite3
    with sqlite3.connect(TEST_DB) as conn:
        conn.execute("DELETE FROM reactions")
        conn.execute("DELETE FROM articles")
        conn.commit()

    for i in range(3):
        article = {
            "title": f"Article {i}",
            "url": f"https://example.com/a{i}",
            "source": f"Source {i % 2}",
            "category": "data_science" if i % 2 == 0 else "software_engineering",
            "relevance_score": 70 + i * 5,
        }
        feedback_store.register_message(1000 + i, article)
        feedback_store.record_reaction(1000 + i, "👍")

    summary = feedback_store.get_summary()
    assert summary["upvoted_count"] == 3
    assert len(summary["top_topics"]) <= 2  # only 2 categories used

    print("✅ test_multiple_articles passed")


def test_dedupe_urls():
    """Test get_sent_urls returns unique normalized URLs."""
    import sqlite3
    with sqlite3.connect(TEST_DB) as conn:
        conn.execute("DELETE FROM reactions")
        conn.execute("DELETE FROM articles")
        conn.commit()

    for i in range(2):
        article = {
            "title": f"Same URL Article {i}",
            "url": "https://example.com/same",  # same URL
            "source": "Test",
            "category": "general_tech",
            "relevance_score": 60,
        }
        feedback_store.register_message(2000 + i, article)

    urls = feedback_store.get_sent_urls()
    assert len(urls) == 1  # deduplicated
    assert "https://example.com/same" in urls

    print("✅ test_dedupe_urls passed")


def test_empty_state():
    """Test summary with no data."""
    import sqlite3
    with sqlite3.connect(TEST_DB) as conn:
        conn.execute("DELETE FROM reactions")
        conn.execute("DELETE FROM articles")
        conn.commit()

    summary = feedback_store.get_summary()
    assert summary["upvoted_count"] == 0
    assert summary["downvoted_count"] == 0
    assert summary["saved_count"] == 0
    assert summary["top_topics"] == []
    assert summary["top_sources"] == []
    assert summary["engagement_rate"] == 0

    saved = feedback_store.get_saved_articles()
    assert saved == []

    urls = feedback_store.get_sent_urls()
    assert urls == set()

    print("✅ test_empty_state passed")


def test_summary_column_and_lookup():
    """register_message stores generated summary; get_article_by_message returns it."""
    import sqlite3
    with sqlite3.connect(TEST_DB) as conn:
        conn.execute("DELETE FROM reactions")
        conn.execute("DELETE FROM articles")
        conn.commit()

    article = {
        "title": "Test Article",
        "url": "https://example.com/article",
        "source": "Test Source",
        "category": "machine_learning / AI",
        "relevance_score": 85,
    }
    generated = "Technical Summary\n\nUseful stuff.\n\n**Why it matters:** Big deal."

    feedback_store.register_message(999888, article, summary=generated)

    row = feedback_store.get_article_by_message(999888)
    assert row is not None
    assert row["title"] == "Test Article"
    assert row["url"] == "https://example.com/article"
    assert row["summary"] == generated
    assert row["relevance_score"] == 85
    print("✅ test_summary_column_and_lookup passed")


def test_get_article_by_message_unknown_id():
    assert feedback_store.get_article_by_message(424242) is None
    print("✅ test_get_article_by_message_unknown_id passed")


def test_old_schema_migration():
    """A DB created with the old (summary-less) schema gets the column added."""
    import sqlite3
    with sqlite3.connect(TEST_DB) as conn:
        conn.execute("DROP TABLE IF EXISTS articles")
        conn.execute("""
            CREATE TABLE articles (
                message_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                url TEXT,
                source TEXT,
                category TEXT,
                relevance_score INTEGER,
                sent_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.commit()

    feedback_store._ensure_schema()  # must migrate without error

    with sqlite3.connect(TEST_DB) as conn:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(articles)").fetchall()}
    assert "summary" in cols
    feedback_store.register_message(777, {"title": "T", "url": "u", "source": "s",
                                          "category": "c", "relevance_score": 1}, summary="x")
    assert feedback_store.get_article_by_message(777)["summary"] == "x"
    print("✅ test_old_schema_migration passed")


if __name__ == "__main__":
    setup_module()
    test_empty_state()
    test_register_and_summary()
    test_multiple_articles()
    test_dedupe_urls()
    test_summary_column_and_lookup()
    test_get_article_by_message_unknown_id()
    test_old_schema_migration()
    teardown_module()
    print("\n🎉 All feedback_store tests passed!")