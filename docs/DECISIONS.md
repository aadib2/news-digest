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

## RSS fetching: shared browser-like `User-Agent` header
- **Decision**: Added a shared `HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; TechDigestBot/1.0)"}` constant used by the `fetch_rss_feed()` helper in `agent/news_fetcher.py` (previously only `GitHubTrendingFetcher` set a UA).
- **Why**: Towards Data Science relaunched as an independent WordPress site in Feb 2025 (moved off Medium) and now blocks requests without a recognizable `User-Agent` (403 Forbidden). Confirmed via curl that the same UA already used for GitHub Trending resolves this. Applied to the shared helper so ArXiv/HackerNews/TLDR are defensively covered too, even though they didn't strictly require it at time of testing.
