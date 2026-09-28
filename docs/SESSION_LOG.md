# Session Log

## 2026-07-20 02:50 UTC
**Focus**: Address `fixes.md` TODOs (per-source article cap + reading-depth balance, feedback persistence), then debug three runtime issues found while testing.

**Changes made**:
1. **Curator source/depth diversity** (`agent/curator_agent.py`, `interests.json`)
   - Added `candidate_pool_size` (20) and `max_per_source` (3) config
   - Prompt now asks Claude for a larger ranked pool with a `reading_time` field (`quick`/`medium`/`deep`) per article
   - Added `_balance_selection()` to deterministically cap articles per source and encourage depth mix, regardless of LLM compliance
   - Increased `max_tokens` 2000 → 5000 to fit the larger candidate response
   - Fixed a latent bug where `raw` could be referenced before assignment in the error-handling path
2. **Feedback persistence migrated to SQLite** (`agent/feedback_store.py`)
   - Replaced `feedback.json` with `articles` + `reactions` tables
   - Kept the same public API (`register_message`, `record_reaction`, `get_summary`, `get_saved_articles`); added `get_sent_urls()` for dedup
   - Fixed a pre-existing bug in `agent/news_fetcher.py` that read the wrong (and env-var-ignoring) path for dedup — now calls `feedback_store.get_sent_urls()`
   - Added `test/test_feedback_store.py` (4 tests, all passing)
   - No migration of old `feedback.json` data (fresh start, per decision)
3. **Deployment pivot: Railway → DigitalOcean Droplet**
   - `feedback_store.py` now reads `DATABASE_PATH` (new, preferred) with `FEEDBACK_DB_PATH` as legacy fallback
   - Added WAL journal mode + 5s busy timeout on every connection
   - Updated `.env.example`, `README.md`, `docs/RUNBOOK.md` accordingly
4. **Debugged & fixed TDS RSS fetcher 403 error**
   - Root cause: no `User-Agent` header on RSS requests; TDS's new independent WordPress site (post Feb-2025 Medium migration) blocks default aiohttp UA
   - Fix: shared `HEADERS` constant applied in `fetch_rss_feed()` helper
5. **Debugged & fixed `bot.py` `PermissionError: /data`**
   - Root cause #1: `load_dotenv()` was called after `agent.*` imports, so `.env` values weren't loaded yet when `feedback_store.py`'s module-level code ran
   - Root cause #2: a stray `FEEDBACK_DB_PATH=/data/feedback.db` was exported in the user's local shell, which `load_dotenv()` doesn't override
   - Fix: moved `load_dotenv()` to the top of `bot.py` (before all `agent.*` imports); user unset the stray shell var locally
6. **Debugged & fixed `ModuleNotFoundError: No module named 'feedback_store'`**
   - Root cause: bare import `from feedback_store import get_sent_urls` in `agent/news_fetcher.py` instead of the package-qualified `from agent.feedback_store import get_sent_urls`
   - Silently caught by a broad `except Exception`, degrading dedup to a no-op
7. Diagnosed a "fix didn't take effect" report as a stale long-running bot process (Python doesn't hot-reload modules) — resolved by fully restarting the process

**Commits this session**: `6b4cfa6`, `f412cce`, `63e3e53`, `91c6781` (see `git log`)

**Verification**: `test/test_curator.py` (JSON extraction: 5/5 pass), `test/test_feedback_store.py` (4/4 pass), `test/test_fetcher.py tds` (fetches articles successfully post-fix). Ranking test against live Claude API not run in this environment (no `ANTHROPIC_API_KEY` set here — expected).

**Secrets check**: `.env` remains untracked (confirmed via `git ls-files`); `*.db`/`*.db-shm`/`*.db-wal` are gitignored. No secrets added to tracked files.
