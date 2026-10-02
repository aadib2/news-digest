# Session Log

## 2026-10-02 07:55 UTC
**Focus**: Close the two follow-ups from the Notion integration session.

**Changes made**:
1. `test/test_notion_client.py` — fixed the stale `Source` (now `select`) and `Status` (`select` / `To Read`) assertions; test credentials are hard-set instead of `setdefault` (shell vars can no longer leak in); the live round-trip is opt-in via `--live` with `load_dotenv(override=True)`; added `test_build_properties_unmapped_source_omits_key`.
2. `agent/notion_client.py` — added `SOURCE_TO_NOTION` (`HackerNews` → `Hacker News`, `Towards Data Science` → `TDS`, others identity); unmapped sources omit the `Source` property instead of auto-creating a Notion option.
3. `docs/RUNBOOK.md`, `docs/DECISIONS.md`, `docs/HANDOFF.md` — replaced the now-closed "known gap" / "not yet fixed" statements.

**Verification**: `test_notion_client` 7/7 in a clean env **and** with `NOTION_DATABASE_ID` / `NOTION_TOKEN` exported (previously failed); `test_summarizer` and `test_feedback_store` still pass. All 5 fetcher source strings are mapped, and every mapping target exists in the live DB's `Source` options. `--live` round-trip not run.

**Secrets check**: no credentials added to tracked files; `.env` untracked.

## 2026-10-02 07:46 UTC
**Focus**: Design, plan, and ship the Notion reading-list integration — a persistent "Save to Notion" button on each digest article — then debug it against the live database.

**Design & planning**:
- Brainstormed the feature (button vs. reaction-hook vs. SDK) and wrote the approved design + full implementation plan to `docs/superpowers/plans/2026-09-13-notion-reading-list-button.md` (7 tasks, TDD steps).
- Key design choices recorded in `docs/DECISIONS.md`: persistent view keyed by a single `custom_id` with a SQLite `message_id → article` lookup (Discord caps `custom_id` at 100 chars), raw REST over aiohttp instead of the sync-only `notion-client` SDK (no new dependency), URL-based dedup before create, and the button doubling as a 🔖 feedback signal.

**Changes made**:
1. **`parse_summary()`** (`agent/summarizer_agent.py`, `test/test_summarizer.py`) — splits Claude's two-part output into `Technical Summary` / `Why It Matters`, tolerating bold/plain markers and the heading; 5 tests, TDD (commit `db92522`).
2. **Summary persistence + message lookup** (`agent/feedback_store.py`, `test/test_feedback_store.py`) — added the `articles.summary` column with an idempotent `_migrate_schema()` (`PRAGMA table_info` guard, since SQLite has no `ADD COLUMN IF NOT EXISTS`), a `summary=` argument on `register_message()`, and `get_article_by_message()`; 4 → 7 tests, TDD (commit `3d746b9`).
3. **Notion client + button wiring** (user-implemented: `df48e9a`, `16f1c0a`, `58ee06b`) — `agent/notion_client.py`, `SaveToNotionView` in `bot.py`, `test/test_notion_client.py`, `test/test_notion_connection.py` (schema inspector), and `NOTION_*` entries in `.env.example`.
4. **Embed-description fallback** (`bot.py`) — when a row's `summary` is empty, the button handler recovers the text from `interaction.message.embeds[0].description`, rescuing the 28 articles posted before the column existed.
5. **Documentation** (`README.md`, `docs/RUNBOOK.md`, `docs/DECISIONS.md`, `docs/HANDOFF.md`) — Notion setup step, env vars, property mapping table, schema-inspection workflow, token rotation, and five new troubleshooting entries.

**Debugging** (systematic, root cause before fix in each case):
1. **`test_create_reading_entry_sends_correct_request` assertion failure** — root cause: `os.environ.setdefault` does not override an existing variable, so a real exported `NOTION_DATABASE_ID` leaked into the test and the payload's `parent` carried the real ID. Reproduced both directions (clean env passes; `NOTION_DATABASE_ID=… uv run …` fails at the exact line). Same family as the July `FEEDBACK_DB_PATH` gotcha. Fix proposed, **not yet applied**.
2. **Duplicated module** — `agent/notion_client.py` contained two concatenated copies of itself; the second silently overrode the first's `STATUS_KEY`/`STATUS_DEFAULT`. De-duplicated by the user.
3. **Live `400 validation_error: "Source is expected to be select"`** — root cause: payload type didn't match the schema (`Source` is a `select`, sent as `rich_text`). Ran the schema inspector for ground truth, which also surfaced `ArticleLink` vs `Article Link` (resolved by renaming the property in Notion) and the latent `Source` option mismatch (`HackerNews` vs `Hacker News`, `Towards Data Science` vs `TDS` — Notion silently auto-creates unknown options).
4. **Blank `Technical Summary` / `Why It Matters` in Notion** — root cause: `bot.py` called `register_message(msg.id, article)` without `summary=summary_text`; confirmed via a read-only DB query showing 0 of 28 rows with a non-empty summary. The downstream chain (`parse_summary("") → ("", "")` → empty rich_text) was behaving correctly on empty input. User applied the one-line fix; agent added the embed fallback.

**Commits this session**: `df48e9a`, `db92522`, `3d746b9`, `16f1c0a`, `58ee06b` (docs + the embed fallback and the live-debugging edits were left uncommitted — see `docs/HANDOFF.md`).

**Verification**: `test/test_summarizer.py` (5/5), `test/test_feedback_store.py` (7/7), `bot.py` AST syntax check, and a simulation of the rescue path (blank-summary row + embed description → populated `Technical Summary` / `Why It Matters` in the real `build_properties()` payload). `test/test_notion_client.py` is **red** (`KeyError: 'rich_text'` at line 65 — stale `Source` assertion). Live verification by the user: button saves to Notion with all fields populated, dedup and the disabled **Saved ✓** state both working.

**Secrets check**: `.env` untracked (confirmed via `git ls-files`); no `NOTION_TOKEN` or `NOTION_DATABASE_ID` values in tracked files — `.env.example` carries empty placeholders and the docs reference variable names only. Schema-inspection output in the docs contains property names only, no credentials.

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
