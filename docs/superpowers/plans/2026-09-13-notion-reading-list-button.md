# Notion Reading-List Button — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a persistent "Save to Notion" button to each digest article message that creates a page in your Notion reading-list database with the article's metadata and Claude summary.

**Architecture:** A persistent `discord.ui.View` (fixed `custom_id`, registered via `bot.add_view()`) rides on every digest message. On click, the handler recovers article metadata from the existing SQLite `articles` table (extended with the generated summary), then calls the Notion REST API through the bot's shared aiohttp session in a new `agent/notion_client.py`. No new dependencies.

**Tech Stack:** discord.py 2.3.2, aiohttp 3.9.5, sqlite3 (stdlib), Notion REST API (`Notion-Version: 2022-06-28`), Python 3.12+ / uv.

## Global Constraints

- **No new dependencies** — Notion calls use the existing aiohttp session; nothing is added to `pyproject.toml`/`requirements.txt`.
- Tests run from project root as `uv run python -m test.<module>` (project pattern — plain asserts + `__main__` runner, no pytest).
- **Never commit `.env`** (contains `NOTION_TOKEN`); only `.env.example` gets placeholders. The user fills real values themselves (AGENTS.md: ask-first for credentials).
- Stage only the exact files listed per commit — never `git add -A`.
- Notion property names in code must exactly match the output of Task 1's inspection script (they're case-sensitive).
- Commit messages match repo style: short sentence-case descriptions (e.g. "Modifying feedback store to SQLite and updating test/config files").
- `docs/` is currently untracked — Task 7 updates doc files but does **not** commit them.

---

### Task 1: Notion integration setup + schema inspection

**Files:**
- Modify: `.env.example` (add two lines)
- No code yet

**Interfaces:**
- Produces: verified facts for Tasks 4–5 — exact property names, the `Status` property **type** (`status` vs `select`), and the `Category` select option names. These determine the `STATUS_KEY` constant and `CATEGORY_TO_NOTION` mapping in Task 4.

- [ ] **Step 1: Create the Notion integration (manual, you do this)**
  1. https://www.notion.so/my-integrations → **New integration** → name it e.g. `news-digest` → submit
  2. Copy the **Internal Integration Secret** → put in `.env` as `NOTION_TOKEN=secret_...`
  3. Open your reading-list database in Notion → **⋯** menu → **Connections** → add the `news-digest` integration
  4. Copy the database ID from the URL (the 32-char hex after the workspace name, before `?v=`) → `.env` as `NOTION_DATABASE_ID=...`
  5. Also add both keys to your droplet's environment when deploying later.

- [ ] **Step 2: Run the schema inspection script**

```bash
uv run python - <<'EOF'
import asyncio, os
from dotenv import load_dotenv
import aiohttp

load_dotenv()
TOKEN = os.environ["NOTION_TOKEN"]
DB_ID = os.environ["NOTION_DATABASE_ID"]

async def main():
    async with aiohttp.ClientSession() as s:
        async with s.get(
            f"https://api.notion.com/v1/databases/{DB_ID}",
            headers={"Authorization": f"Bearer {TOKEN}", "Notion-Version": "2022-06-28"},
        ) as r:
            data = await r.json()
            if r.status != 200:
                print("ERROR", r.status, data)
                return
            for name, prop in data.get("properties", {}).items():
                line = f"{name!r}: {prop['type']}"
                for key in ("select", "status", "multi_select"):
                    if prop["type"] == key:
                        line += " options=" + str([o["name"] for o in prop[key]["options"]])
                print(line)

asyncio.run(main())
EOF
```

Expected: one line per property, e.g. `'Title': title`, `'Article Link': url`, `'Category': select options=['ML/AI', ...]`, `'Status': status options=[...]`, `'Date Added': date`. If you get 401 → bad token; 404 → integration not connected to the database.

- [ ] **Step 3: Record the facts for Tasks 4–5**
  - The **exact** property names for: title, URL, category, source, technical summary, why-it-matters, date-added, status
  - Status property type → `status` or `select`
  - Category option names (for the `CATEGORY_TO_NOTION` mapping)

- [ ] **Step 4: Update `.env.example`** — append:

```
NOTION_TOKEN="" # Notion internal integration secret (notion.so/my-integrations)
NOTION_DATABASE_ID="" # Reading-list database ID (32-char hex in the DB URL)
```

- [ ] **Step 5: Commit**

```bash
git add .env.example
git commit -m "Add Notion env vars to .env.example for reading-list integration"
```

---

### Task 2: `parse_summary()` in the summarizer agent

**Files:**
- Modify: `agent/summarizer_agent.py` (add module-level function above `SummarizerAgent`)
- Create: `test/test_summarizer.py`

**Interfaces:**
- Produces: `parse_summary(summary_text: str) -> tuple[str, str]` — splits the summarizer's two-part output into `(technical_summary, why_it_matters)`. Consumed by `agent/notion_client.py` in Task 4. Pure function — no API key needed to test.

- [ ] **Step 1: Write the failing tests** — create `test/test_summarizer.py`:

```python
"""
test_summarizer.py
Unit tests for parse_summary() — splitting Claude's digest summary into
its Technical Summary and Why It Matters parts.
Run: uv run python -m test.test_summarizer
"""

from agent.summarizer_agent import parse_summary


def test_typical_output():
    text = (
        "Technical Summary\n\n"
        "Transformers process tokens in parallel using self-attention. "
        "This paper introduces a linear-time variant.\n\n"
        "**Why it matters:** Faster attention cuts inference cost for on-device ML."
    )
    tech, why = parse_summary(text)
    assert "Transformers" in tech
    assert "Technical Summary" not in tech
    assert why == "Faster attention cuts inference cost for on-device ML."
    print("✅ test_typical_output passed")


def test_case_insensitive_marker():
    text = "Something useful.\n\n**Why It Matters:** Big deal for RAG pipelines."
    tech, why = parse_summary(text)
    assert tech == "Something useful."
    assert why == "Big deal for RAG pipelines."
    print("✅ test_case_insensitive_marker passed")


def test_unbolded_marker():
    text = "Something useful.\n\nWhy it matters: Big deal."
    tech, why = parse_summary(text)
    assert tech == "Something useful."
    assert why == "Big deal."
    print("✅ test_unbolded_marker passed")


def test_no_marker_falls_back():
    text = "Only a technical summary with no takeaway sentence."
    tech, why = parse_summary(text)
    assert tech == text
    assert why == ""
    print("✅ test_no_marker_falls_back passed")


def test_empty_and_fallback_text():
    assert parse_summary("") == ("", "")
    assert parse_summary("No preview available - check link for more info.") == (
        "No preview available - check link for more info.", ""
    )
    print("✅ test_empty_and_fallback_text passed")


if __name__ == "__main__":
    test_typical_output()
    test_case_insensitive_marker()
    test_unbolded_marker()
    test_no_marker_falls_back()
    test_empty_and_fallback_text()
    print("\n🎉 All summarizer parse tests passed!")
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run python -m test.test_summarizer`
Expected: `ImportError: cannot import name 'parse_summary'`

- [ ] **Step 3: Implement** — add to `agent/summarizer_agent.py` (module level, after imports):

```python
_WHY_MARKER = "why it matters:"


def _strip_heading(text: str) -> str:
    """Remove a leading 'Technical Summary' style heading and bold markers."""
    if text.lower().startswith("technical summary"):
        text = text[len("technical summary"):]
    return text.strip().lstrip("*:-# \n").strip()


def parse_summary(summary_text: str) -> tuple[str, str]:
    """Split a summarizer output into (technical_summary, why_it_matters).

    Tolerates bold/plain markers and a 'Technical Summary' heading.
    If no 'why it matters' marker is found, the whole text is the
    technical summary and the takeaway is empty.
    """
    if not summary_text:
        return "", ""
    idx = summary_text.lower().find(_WHY_MARKER)
    if idx == -1:
        return _strip_heading(summary_text), ""
    technical = _strip_heading(summary_text[:idx].rstrip("*").rstrip())
    why = summary_text[idx + len(_WHY_MARKER):].lstrip("* ").strip()
    return technical, why
```

- [ ] **Step 4: Run tests — all pass**

Run: `uv run python -m test.test_summarizer`
Expected: `🎉 All summarizer parse tests passed!`

- [ ] **Step 5: Commit**

```bash
git add agent/summarizer_agent.py test/test_summarizer.py
git commit -m "Add parse_summary to split digest summaries for Notion export"
```

---

### Task 3: Persist the generated summary + message lookup in feedback store

**Files:**
- Modify: `agent/feedback_store.py` (schema, migration, `register_message`, new `get_article_by_message`)
- Modify: `test/test_feedback_store.py` (extend)

**Interfaces:**
- Produces (used by Task 5's button handler):
  - `register_message(message_id: int, article: Dict, summary: str = "")` — backward-compatible new kwarg; stores the **Claude-generated** summary (not the article's source preview).
  - `get_article_by_message(message_id: int) -> Optional[Dict]` — returns `{"title", "url", "source", "category", "relevance_score", "summary"}` or `None` if the message ID is unknown.

- [ ] **Step 1: Write the failing tests** — append to `test/test_feedback_store.py` (and register in `__main__`):

```python
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
```

Also update `__main__` to call the three new tests, and refresh the schema in `setup_module`-style `DELETE`s as the existing tests do.

- [ ] **Step 2: Run to verify failure**

Run: `uv run python -m test.test_feedback_store`
Expected: FAIL on the new tests (`TypeError: register_message() takes 2 positional arguments` / `AttributeError: get_article_by_message`)

- [ ] **Step 3: Implement in `agent/feedback_store.py`:**

1. `CREATE TABLE articles` statement: add `summary TEXT NOT NULL DEFAULT ''` after `relevance_score`.
2. New migration helper, called from `_ensure_schema()` after the `CREATE` statements:

```python
def _migrate_schema():
    """Add columns introduced after initial release (idempotent)."""
    with _db() as conn:
        cols = {row["name"] for row in conn.execute("PRAGMA table_info(articles)").fetchall()}
        if "summary" not in cols:
            conn.execute("ALTER TABLE articles ADD COLUMN summary TEXT NOT NULL DEFAULT ''")
```

3. `register_message` — new optional param, add to the `INSERT OR REPLACE` column list and values tuple:

```python
def register_message(message_id: int, article: Dict, summary: str = ""):
    """Map a Discord message ID to the article it represents.

    `summary` is the Claude-generated digest summary (not the source preview).
    """
    with _db() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO articles
                (message_id, title, url, source, category, relevance_score, summary)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(message_id),
                article.get("title", ""),
                article.get("url", ""),
                article.get("source", ""),
                article.get("category", ""),
                article.get("relevance_score", 0),
                summary,
            ),
        )
```

4. New lookup:

```python
def get_article_by_message(message_id: int) -> Optional[Dict]:
    """Return the stored article metadata for a digest message, or None."""
    with _db() as conn:
        row = conn.execute(
            """
            SELECT title, url, source, category, relevance_score, summary
            FROM articles WHERE message_id = ?
            """,
            (str(message_id),),
        ).fetchone()
    if row is None:
        return None
    return {
        "title": row["title"],
        "url": row["url"],
        "source": row["source"],
        "category": row["category"],
        "relevance_score": row["relevance_score"],
        "summary": row["summary"],
    }
```

5. Add `Optional` to the `typing` import line (currently `from typing import Dict, List, Set`).

- [ ] **Step 4: Run tests — all pass** (old tests unaffected; new `summary` kwarg is optional)

Run: `uv run python -m test.test_feedback_store`
Expected: `🎉 All feedback_store tests passed!` (7 tests)

- [ ] **Step 5: Commit**

```bash
git add agent/feedback_store.py test/test_feedback_store.py
git commit -m "Persist generated summaries in feedback store and add message lookup"
```

---

### Task 4: Notion REST client

**Files:**
- Create: `agent/notion_client.py`
- Create: `test/test_notion_client.py`

**Interfaces:**
- Consumes: `parse_summary` from Task 2; article dicts shaped like `get_article_by_message`'s return (Task 3).
- Produces (used by Task 5):
  - `class NotionNotConfigured(RuntimeError)`
  - `async create_reading_entry(session: aiohttp.ClientSession, article: dict) -> dict` — creates the page, returns Notion's page JSON
  - `async url_exists(session: aiohttp.ClientSession, url: str) -> bool` — duplicate check
  - `build_properties(article: dict) -> dict` — pure payload builder (testable without HTTP)

- [ ] **Step 1: Write the failing tests** — create `test/test_notion_client.py`:

```python
"""
test_notion_client.py
Unit tests for the Notion client (mocked aiohttp) + optional live round-trip.
Run: uv run python -m test.test_notion_client
Live round-trip only runs if NOTION_TOKEN/NOTION_DATABASE_ID are set.
"""

import os

# Test credentials so _config() passes without real secrets
os.environ.setdefault("NOTION_TOKEN", "secret_test_token")
os.environ.setdefault("NOTION_DATABASE_ID", "0" * 32)

import aiohttp

from agent.notion_client import (
    NotionNotConfigured, build_properties, create_reading_entry, url_exists,
)
from agent.summarizer_agent import parse_summary

ARTICLE = {
    "title": "Linear Attention Is All You Need",
    "url": "https://example.com/linear-attention",
    "source": "HackerNews",
    "category": "machine_learning / AI",
    "relevance_score": 92,
    "summary": "Technical Summary\n\nLinear attention runs in O(n).\n\n**Why it matters:** Cheaper inference.",
}


class FakeResponse:
    def __init__(self, status=200, json_data=None, text_data=""):
        self.status = status
        self._json = json_data or {}
        self._text = text_data

    async def json(self):
        return self._json

    async def text(self):
        return self._text

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


class FakeSession:
    """Stand-in for aiohttp.ClientSession that records calls."""
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def post(self, url, json=None, headers=None):
        self.calls.append({"url": url, "json": json, "headers": headers})
        return self.responses.pop(0)


def test_build_properties():
    props = build_properties(ARTICLE)
    assert props["Title"]["title"][0]["text"]["content"] == ARTICLE["title"]
    assert props["Article Link"]["url"] == ARTICLE["url"]
    assert props["Source"]["rich_text"][0]["text"]["content"] == "HackerNews"
    assert props["Category"]["select"]["name"] == "ML/AI"
    assert props["Technical Summary"]["rich_text"][0]["text"]["content"] == "Linear attention runs in O(n)."
    assert props["Why It Matters"]["rich_text"][0]["text"]["content"] == "Cheaper inference."
    assert props["Status"]["status"]["name"] == "to read"
    assert props["Date Added"]["date"]["start"]
    print("✅ test_build_properties passed")


def test_build_properties_unknown_category_omits_key():
    article = dict(ARTICLE, category="")
    assert "Category" not in build_properties(article)
    print("✅ test_build_properties_unknown_category_omits_key passed")


def test_create_reading_entry_sends_correct_request():
    session = FakeSession(FakeResponse(200, {"id": "page-1", "url": "https://notion.so/page-1"}))
    import asyncio
    page = asyncio.run(create_reading_entry(session, ARTICLE))
    call = session.calls[0]
    assert call["url"] == "https://api.notion.com/v1/pages"
    assert call["json"]["parent"] == {"database_id": "0" * 32}
    assert call["json"]["properties"]["Article Link"]["url"] == ARTICLE["url"]
    assert call["headers"]["Notion-Version"] == "2022-06-28"
    assert call["headers"]["Authorization"] == "Bearer secret_test_token"
    assert page["id"] == "page-1"
    print("✅ test_create_reading_entry_sends_correct_request passed")


def test_create_reading_entry_raises_on_error():
    session = FakeSession(FakeResponse(400, text_data='{"message": "Property Title not found"}'))
    import asyncio
    try:
        asyncio.run(create_reading_entry(session, ARTICLE))
        assert False, "should have raised"
    except RuntimeError as e:
        assert "400" in str(e) and "Title not found" in str(e)
    print("✅ test_create_reading_entry_raises_on_error passed")


def test_url_exists():
    session = FakeSession(FakeResponse(200, {"results": [{"id": "existing"}]}))
    assert asyncio_run(url_exists(session, ARTICLE["url"])) is True
    q = session.calls[0]["json"]
    assert q["filter"] == {"property": "Article Link", "url": {"equals": ARTICLE["url"]}}

    session2 = FakeSession(FakeResponse(200, {"results": []}))
    assert asyncio_run(url_exists(session2, "https://new.example.com")) is False
    print("✅ test_url_exists passed")


def asyncio_run(coro):
    import asyncio
    return asyncio.run(coro)


def test_not_configured():
    token, db = os.environ.pop("NOTION_TOKEN"), os.environ.pop("NOTION_DATABASE_ID")
    try:
        import asyncio
        asyncio.run(url_exists(FakeSession(), "https://x.example.com"))
        assert False, "should have raised"
    except NotionNotConfigured:
        pass
    finally:
        os.environ["NOTION_TOKEN"], os.environ["NOTION_DATABASE_ID"] = token, db
    print("✅ test_not_configured passed")


def live_round_trip():
    """Creates a clearly-marked test page, checks dedup, then archives it."""
    import asyncio
    from dotenv import load_dotenv
    load_dotenv()

    async def run():
        async with aiohttp.ClientSession() as s:
            article = dict(ARTICLE, url="https://example.com/news-digest-test")
            page = await create_reading_entry(s, article)
            print(f"  created page: {page['url']}")
            assert await url_exists(s, article["url"]) is True, "dedup check should find it"
            async with s.patch(
                f"https://api.notion.com/v1/pages/{page['id']}",
                json={"archived": True},
                headers={
                    "Authorization": f"Bearer {os.environ['NOTION_TOKEN']}",
                    "Notion-Version": "2022-06-28",
                },
            ) as r:
                assert r.status == 200, await r.text()
            assert await url_exists(s, article["url"]) is False, "archived page should not match"

    asyncio.run(run())
    print("✅ live_round_trip passed")


if __name__ == "__main__":
    test_build_properties()
    test_build_properties_unknown_category_omits_key()
    test_create_reading_entry_sends_correct_request()
    test_create_reading_entry_raises_on_error()
    test_url_exists()
    test_not_configured()
    print("\n🎉 All notion_client tests passed!")
    if os.getenv("NOTION_TOKEN", "").startswith("secret_") and \
       os.getenv("NOTION_TOKEN") != "secret_test_token":
        print("\n— Live round-trip (real Notion) —")
        live_round_trip()
```

Note: `Status` in `test_build_properties` asserts key `"status"` — **adjust to `"select"` here and in the client if Task 1's inspection showed `select`**. Same for `Category` option names.

- [ ] **Step 2: Run to verify failure**

Run: `uv run python -m test.test_notion_client`
Expected: `ModuleNotFoundError: No module named 'agent.notion_client'`

- [ ] **Step 3: Implement** — create `agent/notion_client.py`:

```python
"""
notion_client.py
Thin async client for the Notion REST API. Creates reading-list pages
from digest articles using the bot's shared aiohttp session.
"""

import os
from datetime import datetime, timezone

import aiohttp

from agent.summarizer_agent import parse_summary

NOTION_API_BASE = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"

# Bot categories → Notion Category options (from Task 1's inspection)
CATEGORY_TO_NOTION = {
    "machine_learning / AI": "ML/AI",
    "data_science": "Data Science",
    "software_engineering": "SWE",
    "general_tech": "General Tech",
}
STATUS_KEY = "status"  # "status" or "select" — from Task 1's inspection
STATUS_DEFAULT = "to read"


class NotionNotConfigured(RuntimeError):
    """Raised when NOTION_TOKEN or NOTION_DATABASE_ID is not set."""


def _config():
    """Return (token, database_id) or raise NotionNotConfigured."""
    token = os.getenv("NOTION_TOKEN")
    database_id = os.getenv("NOTION_DATABASE_ID")
    if not token or not database_id:
        raise NotionNotConfigured("Set NOTION_TOKEN and NOTION_DATABASE_ID in .env")
    return token, database_id


def _headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


def build_properties(article: dict) -> dict:
    """Build the Notion page `properties` payload for a digest article."""
    technical, why_it_matters = parse_summary(article.get("summary", ""))
    props = {
        "Title": {"title": [{"text": {"content": article.get("title", "")[:2000]}}]},
        "Article Link": {"url": article.get("url", "")},
        "Source": {"rich_text": [{"text": {"content": article.get("source", "")}}]},
        "Technical Summary": {"rich_text": [{"text": {"content": technical[:2000]}}]},
        "Why It Matters": {"rich_text": [{"text": {"content": why_it_matters[:2000]}}]},
        "Date Added": {"date": {"start": datetime.now(timezone.utc).isoformat()}},
        "Status": {STATUS_KEY: {"name": STATUS_DEFAULT}},
    }
    category = CATEGORY_TO_NOTION.get(article.get("category", ""), "")
    if category:
        props["Category"] = {"select": {"name": category}}
    return props


async def create_reading_entry(session: aiohttp.ClientSession, article: dict) -> dict:
    """Create a page in the reading-list database. Returns the created page JSON."""
    token, database_id = _config()
    payload = {"parent": {"database_id": database_id}, "properties": build_properties(article)}
    async with session.post(
        f"{NOTION_API_BASE}/pages", json=payload, headers=_headers(token)
    ) as resp:
        if resp.status != 200:
            body = await resp.text()
            raise RuntimeError(f"Notion create failed ({resp.status}): {body[:300]}")
        return await resp.json()


async def url_exists(session: aiohttp.ClientSession, url: str) -> bool:
    """True if a reading-list page already has this URL (duplicate check)."""
    if not url:
        return False
    token, database_id = _config()
    payload = {
        "filter": {"property": "Article Link", "url": {"equals": url}},
        "page_size": 1,
    }
    async with session.post(
        f"{NOTION_API_BASE}/databases/{database_id}/query",
        json=payload,
        headers=_headers(token),
    ) as resp:
        if resp.status != 200:
            body = await resp.text()
            raise RuntimeError(f"Notion query failed ({resp.status}): {body[:300]}")
        data = await resp.json()
    return bool(data.get("results"))
```

- [ ] **Step 4: Run tests — all pass**

Run: `uv run python -m test.test_notion_client`
Expected: `🎉 All notion_client tests passed!` (6 tests; live round-trip skipped unless real creds set)

- [ ] **Step 5: Run the live round-trip (optional, needs Task 1 creds)**

Run: `uv run python -m test.test_notion_client` with real `NOTION_TOKEN`/`NOTION_DATABASE_ID` in `.env`
Expected: live section creates a page in your reading list, dedup check finds it, archives it, dedup check no longer matches. **A 400 here means a property name/type mismatch — fix the name in `build_properties` + test per Task 1's inspection output.**

- [ ] **Step 6: Commit**

```bash
git add agent/notion_client.py test/test_notion_client.py
git commit -m "Add Notion REST client for reading-list page creation"
```

---

### Task 5: Wire the persistent button into the bot

**Files:**
- Modify: `bot.py` (imports, view class, `setup_hook`, `send_digest`, `/help` copy)

**Interfaces:**
- Consumes: `SaveToNotionView` needs `feedback_store.get_article_by_message`, `feedback_store.record_reaction`, `notion_client.create_reading_entry`, `notion_client.url_exists`, `notion_client.NotionNotConfigured`.
- Produces: user-facing behavior — every digest article message carries a working "🔖 Save to Notion" button that survives restarts.

No automated tests for the Discord layer (project has no discord test harness) — verified manually in Task 6. All existing tests must still pass.

- [ ] **Step 1: Add imports** in `bot.py` (next to the other `agent` imports, after `load_dotenv()`):

```python
import agent.notion_client as notion_client
from agent.notion_client import NotionNotConfigured
```

- [ ] **Step 2: Add the view** (after `CATEGORY_META` / before `send_digest`):

```python
SAVE_BUTTON_CUSTOM_ID = "news-digest:save-to-notion"


class SaveToNotionView(discord.ui.View):
    """Persistent 'Save to Notion' button attached to each digest article."""

    def __init__(self, *, saved: bool = False):
        super().__init__(timeout=None)
        for child in self.children:
            if getattr(child, "custom_id", None) == SAVE_BUTTON_CUSTOM_ID:
                child.disabled = saved
                child.label = "Saved ✓" if saved else "Save to Notion"

    @discord.ui.button(
        label="Save to Notion",
        emoji="🔖",
        style=discord.ButtonStyle.gray,
        custom_id=SAVE_BUTTON_CUSTOM_ID,
    )
    async def save_to_notion(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """Save the article behind this message to the Notion reading list."""
        await interaction.response.defer(ephemeral=True, thinking=True)

        article = feedback_store.get_article_by_message(interaction.message.id)
        if article is None:
            await interaction.followup.send(
                "Couldn't find this article's metadata "
                "(it may predate the Notion feature).",
                ephemeral=True,
            )
            return

        try:
            if await notion_client.url_exists(aiohttp_session, article["url"]):
                await interaction.message.edit(view=SaveToNotionView(saved=True))
                feedback_store.record_reaction(interaction.message.id, "🔖")
                await interaction.followup.send(
                    "Already in your Notion reading list ✓", ephemeral=True
                )
                return

            await notion_client.create_reading_entry(aiohttp_session, article)
            feedback_store.record_reaction(interaction.message.id, "🔖")
            await interaction.message.edit(view=SaveToNotionView(saved=True))
            await interaction.followup.send(
                "Saved to your Notion reading list ✓", ephemeral=True
            )
            print(f"[Notion] Saved: {article['title'][:60]}")
        except NotionNotConfigured:
            await interaction.followup.send(
                "Notion isn't configured — set NOTION_TOKEN and "
                "NOTION_DATABASE_ID in .env and restart.",
                ephemeral=True,
            )
        except Exception as e:
            print(f"[Notion] Error saving article: {e}")
            await interaction.followup.send(
                f"Couldn't save to Notion ({str(e)[:150]}). Try again.",
                ephemeral=True,
            )
```

Notes: `timeout=None` + fixed `custom_id` = persistent (works on old messages after restarts, per discord.py docs). The `saved=True` instance is only used to *render* the disabled state — the disabled flag persists in Discord's message JSON after `message.edit`.

- [ ] **Step 3: Register the view once, before the gateway connects** — add after `async def _close_aiohttp_session()`:

```python
@bot.event
async def setup_hook():
    """Register persistent views before the gateway connects."""
    bot.add_view(SaveToNotionView())
```

- [ ] **Step 4: Update `send_digest`** — two changes in the article loop:
  - `msg = await channel.send(embed=embed, view=SaveToNotionView())`
  - `feedback_store.register_message(msg.id, article, summary=summary_text)`

- [ ] **Step 5: Update copy** (small, so the UX is self-explanatory):
  - Header embed description line → `"React with 👍 upvote · 👎 downvote · 🔖 save — or use 🔖 **Save to Notion** to add to your reading list"`
  - `/help`: add a field — name `"Save to Notion"`, value `"The button on each article saves it to the connected Notion reading list"`

- [ ] **Step 6: Run the full test suite**

Run: `uv run python -m test.test_summarizer && uv run python -m test.test_feedback_store && uv run python -m test.test_notion_client`
Expected: all pass (proves no import/side-effect breakage in `bot.py`'s dependencies).

Also: `uv run python -c "import ast; ast.parse(open('bot.py').read())"` — syntax check without launching the bot.

- [ ] **Step 7: Commit**

```bash
git add bot.py
git commit -m "Add persistent Save to Notion button to digest messages"
```

---

### Task 6: Live end-to-end verification (manual)

**Files:** none (verification only)

- [ ] **Step 1: Happy path** — `uv run python bot.py` with real `.env` (Discord + Notion), run `/digest` in your channel, click the button on an article:
  - Ephemeral "Saved to your Notion reading list ✓"
  - Button becomes disabled "Saved ✓" on the message
  - Notion page appears with Title, Article Link, Category, Source, Technical Summary, Why It Matters, Date Added, Status=`to read`
- [ ] **Step 2: Dedup path** — click the same button on a different article that has the same URL sent in a previous digest, or re-run `/digest` and click a repeat: expect "Already in your Notion reading list ✓" and only **one** page in Notion.
- [ ] **Step 3: Restart persistence** — restart the bot, then click a still-enabled button on a message from *before* the restart: it must still work (validates `setup_hook` registration + SQLite lookup).
- [ ] **Step 4: Unconfigured path** — stop bot, temporarily rename `.env`'s `NOTION_TOKEN`, start, click: expect the "Notion isn't configured…" ephemeral message and the button stays enabled. Restore `.env`.
- [ ] **Step 5: Curator feedback integration** — after a successful button save, run `/stats`: `🔖 Saved` count incremented by 1 (validates the 🔖-equivalent reaction recording).
- [ ] **Step 6: Old-message path** — click the button on a digest message from *before* this feature shipped (no stored metadata or no button — if a pre-feature message somehow has a button, expect the "couldn't find metadata" ephemeral reply; pre-feature messages have no button at all, which is fine).

---

### Task 7: Docs + session bookkeeping

**Files:**
- Modify: `README.md`, `docs/RUNBOOK.md`, `docs/DECISIONS.md`, `docs/HANDOFF.md`, `docs/SESSION_LOG.md`
- Commit only `README.md` (docs/ is deliberately untracked)

- [ ] **Step 1: README.md**
  - `.env` block in Setup Step 4: add `NOTION_TOKEN` and `NOTION_DATABASE_ID` lines
  - New setup sub-step (after Step 3): "Create a Notion integration, share your reading-list database with it, put the token + database ID in `.env`" (mirroring Task 1)
  - Usage table: add row `| 🔖 Save to Notion button | Saves the article to your Notion reading list |`
  - Troubleshooting: add "**Button says Notion isn't configured** → set `NOTION_TOKEN`/`NOTION_DATABASE_ID`, ensure the DB is shared with the integration" and "**Notion 400 error** → property names in `agent/notion_client.py` must match your database exactly"

- [ ] **Step 2: docs/RUNBOOK.md** — new "## Notion Reading-List Integration" section: the two env vars, how to rotate the token, where property mappings live (`CATEGORY_TO_NOTION`, `STATUS_KEY` in `agent/notion_client.py`), and the dedup mechanism (URL query before create).

- [ ] **Step 3: docs/DECISIONS.md** — new entry: persistent single-`custom_id` view + SQLite message→article lookup (vs. encoding data in `custom_id`'s 100-char limit); aiohttp over `notion-client` SDK (no new sync-only dependency); button click records a 🔖-equivalent reaction so the curator learns from saves; URL-based dedup.

- [ ] **Step 4: Session-end protocol (AGENTS.md)** — update `docs/HANDOFF.md` (timestamp `YYYY-MM-DD HH:MM UTC`, current state, top 3 next actions, blockers), append a timestamped entry to `docs/SESSION_LOG.md`, and confirm no secrets were added to tracked files (`git diff --staged` review — `NOTION_TOKEN` only ever lives in `.env`).

- [ ] **Step 5: Commit**

```bash
git add README.md
git commit -m "Document Notion reading-list integration and env vars"
```

---

## Notes

- **Anyone in the channel can click the button** (it saves to *your* list and the clicker sees the confirmation). For a personal bot that's fine; to restrict it to yourself, add an `interaction.user.id` check at the top of the callback.
- Task 1's inspection output is the source of truth for property names, `STATUS_KEY`, and `CATEGORY_TO_NOTION` — Task 4's code and tests use defaults that must be reconciled against it.
