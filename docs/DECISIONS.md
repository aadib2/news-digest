# Decisions

## Curator: hybrid prompt + deterministic enforcement for source/depth diversity
- **Decision**: Ask Claude to rank a larger candidate pool (`candidate_pool_size`, default 20) instead of just the final digest size, then deterministically enforce `max_per_source` (default 3) and reading-depth mix in Python (`_balance_selection` in `agent/curator_agent.py`).
- **Why**: Prompt-only guidance isn't guaranteed to be followed by the LLM. A Python-side cap guarantees no single source (e.g. ArXiv) can dominate the digest, regardless of model compliance.
- **Follow-on**: Claude now also returns a `reading_time` field (`quick`/`medium`/`deep`) per article so depth balancing doesn't rely solely on a source→depth heuristic.

## Feedback persistence: SQLite instead of JSON file
- **Decision**: Replaced the single `feedback.json` blob with a SQLite database (`articles` + `reactions` tables) in `agent/feedback_store.py`.
- **Why**: Avoids full read-modify-write of a growing JSON file on every reaction; gets transactional writes, indexed lookups, and simple aggregate queries (`get_summary`, `get_sent_urls`) for free. No new dependency (`sqlite3` is stdlib).
- **No data migration**: Old `feedback.json` data was intentionally not migrated — fresh start, since the JSON store wasn't reliably updating in the old Railway deployment anyway. A manual migration snippet exists in `docs/RUNBOOK.md` if ever needed.

## Deployment target changed: Railway → DigitalOcean Droplet
- **Decision**: `agent/feedback_store.py` now reads the DB path from `DATABASE_PATH` (new, preferred) with `FEEDBACK_DB_PATH` kept only as a legacy fallback. WAL journal mode + a 5s busy timeout are set on every connection.
- **Why**: Droplet deployment uses a plain filesystem path rather than a Railway-style mounted volume, so the path just needs to be a writable directory on the droplet (e.g. `/data/feedback.db`), created automatically via `DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)`.
- **Gotcha discovered**: `python-dotenv`'s `load_dotenv()` does not override already-exported shell environment variables. A stray `FEEDBACK_DB_PATH=/data/feedback.db` left in a local shell silently overrides `.env`, which caused a local `PermissionError` trying to create `/data` at filesystem root. Keep local shells clean of leftover deployment env vars.

## `load_dotenv()` must run before any `agent.*` imports in `bot.py`
- **Decision**: Moved `from dotenv import load_dotenv; load_dotenv()` to the very top of `bot.py`, before importing `agent.feedback_store` and friends.
- **Why**: `agent/feedback_store.py` reads `DATABASE_PATH`/`FEEDBACK_DB_PATH` at **module level** (import time). If `load_dotenv()` runs after that import, `.env` values aren't in the process environment yet, so the module silently falls back to whatever's already set in the shell (or the hardcoded default).

## Internal package imports must use the `agent.` prefix
- **Decision**: All intra-package imports use `from agent.<module> import ...` (absolute), matching how `agent/` is structured as a real package (`agent/__init__.py` exists) and how `bot.py` already imports it.
- **Why**: A bare `from feedback_store import get_sent_urls` inside `agent/news_fetcher.py` raised `ModuleNotFoundError: No module named 'feedback_store'` because `agent/` isn't on `sys.path` directly — only the project root is. This was masked by a broad `except Exception` that silently degraded dedup to a no-op.

## Notion saves: persistent Discord button + SQLite message→article lookup
- **Decision**: Each digest message carries a persistent `discord.ui.View` (`SaveToNotionView` in `bot.py`) with a single fixed `custom_id`, registered once via `bot.add_view()`. The click handler recovers the article by looking up `interaction.message.id` in the existing `articles` table.
- **Why**: Discord's `custom_id` is capped at 100 characters — not enough for a URL plus metadata — and we already persist a `message_id → article` mapping for feedback. `timeout=None` + fixed `custom_id` means buttons keep working on old messages across bot restarts, with no per-message state held in memory.
- **Follow-on**: After a successful save the message is edited to a disabled **Saved ✓** button; that state lives in Discord's message JSON, so it also survives restarts.

## Notion client: raw REST over aiohttp, not the `notion-client` SDK
- **Decision**: `agent/notion_client.py` talks to the Notion REST API directly using the bot's shared aiohttp session, with `Notion-Version` pinned to `2022-06-28`.
- **Why**: No new dependency (the official SDK is sync-only and would need `asyncio.to_thread` wrapping), and it matches how `news_fetcher.py` already consumes the shared session. The client is thin enough (~90 lines) that the SDK buys nothing.

## Notion payload must mirror the database schema; the inspection script is the source of truth
- **Decision**: `test/test_notion_connection.py` prints every property name, type, and select option; `build_properties()` is written against that output rather than against assumptions.
- **Why**: Notion validates each property's payload shape against the schema and rejects mismatches with `400 validation_error` (hit live as `"Source is expected to be select"` when `Source` was sent as `rich_text`). Property names are case- and space-sensitive (`Article Link` vs `ArticleLink` produced a second failure), and names appear in two places — `build_properties()` and the `url_exists()` filter.
- **Select options**: unknown *select option* names do **not** error — Notion auto-creates the option. `SOURCE_TO_NOTION` maps the fetcher's names (`HackerNews`, `Towards Data Science`) to the DB's options (`Hacker News`, `TDS`), and unmapped sources are omitted (same as `Category`) so a new fetcher can't silently fork the options.

## Button click also records a 🔖 reaction
- **Decision**: A successful (or already-saved) Notion save calls `record_reaction(message_id, "🔖")` in addition to writing to Notion.
- **Why**: Saving is the strongest positive signal the user gives. One gesture feeds both the external reading list and the curator's feedback context, instead of requiring a separate 🔖 reaction. `/saved` and `/stats` keep working unchanged.

## Dedup on the article URL, checked before create
- **Decision**: `url_exists()` queries the database filtered on `Article Link == url` before creating a page.
- **Why**: Notion has no unique constraints, and the same URL can resurface across digests. Checking by URL (rather than tracking saved message IDs locally) also catches articles added to the reading list by other means.

## Generated summaries are persisted at digest time, with an embed fallback for older messages
- **Decision**: `register_message()` takes the Claude-generated summary as an explicit `summary=` argument (stored in a new `articles.summary` column, added via an idempotent `_migrate_schema()`). The button handler falls back to the Discord embed's description when that column is empty.
- **Why**: The article dict's own `summary` key holds the *source preview*, not the generated two-part summary — storing it would have exported the wrong text to Notion. The generated text previously existed only as the embed description, so nothing persisted it. The fallback rescues the 28 articles sent before the column existed (their text is still in the embeds) and permanently covers pre-feature messages.

## RSS fetching: shared browser-like `User-Agent` header
- **Decision**: Added a shared `HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; TechDigestBot/1.0)"}` constant used by the `fetch_rss_feed()` helper in `agent/news_fetcher.py` (previously only `GitHubTrendingFetcher` set a UA).
- **Why**: Towards Data Science relaunched as an independent WordPress site in Feb 2025 (moved off Medium) and now blocks requests without a recognizable `User-Agent` (403 Forbidden). Confirmed via curl that the same UA already used for GitHub Trending resolves this. Applied to the shared helper so ArXiv/HackerNews/TLDR are defensively covered too, even though they didn't strictly require it at time of testing.
