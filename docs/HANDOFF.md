# Handoff

**Last updated**: 2026-07-20 02:50 UTC

## Current State
- Curator now enforces a per-source article cap (`max_per_source: 3`) and reading-depth balance (`quick`/`medium`/`deep`) via a hybrid prompt + deterministic post-filter (`agent/curator_agent.py`), configured through `interests.json` (`candidate_pool_size`, `max_per_source`).
- Feedback storage fully migrated from `feedback.json` to SQLite (`agent/feedback_store.py`), with the DB path configurable via `DATABASE_PATH` (legacy `FEEDBACK_DB_PATH` still supported as a fallback), WAL mode, and a 5s busy timeout. `agent/news_fetcher.py` correctly dedupes against previously-sent articles via `feedback_store.get_sent_urls()`.
- Deployment target is now a **DigitalOcean Droplet** (moved off Railway) — code no longer assumes a Railway-style mounted volume; the DB directory is auto-created at the configured `DATABASE_PATH`.
- Three runtime bugs found and fixed this session: TDS RSS 403 (missing `User-Agent`), `bot.py` env-loading order (`load_dotenv()` ran too late), and a bare/incorrect import (`feedback_store` vs `agent.feedback_store`) that silently broke dedup.
- All changes are committed (see `docs/SESSION_LOG.md` for commit hashes). Working tree is otherwise clean except for untracked scratch files (`dummy.py`, `hello.py`, `fixes.md`, `logs/`).
- The reaction buttons (👍👎🔖 auto-add) in `bot.py` remain intentionally commented out — user is managing that toggle themselves.

## Top 3 Next Actions
1. **Deploy to the DigitalOcean Droplet**: set `DATABASE_PATH` (e.g. `/data/feedback.db`) in the droplet's real environment, confirm the bot process's user can write to that directory, and roll out the latest commits.
2. **End-to-end smoke test in production-like conditions**: trigger `/digest` on the droplet and confirm (a) the curator returns a diverse, capped-per-source digest with sensible reading-depth mix, and (b) reactions persist correctly across a bot restart (validates the SQLite + `DATABASE_PATH` setup holds up outside this dev environment).
3. **Decide on re-enabling auto-added reactions**: `bot.py`'s 👍👎🔖 auto-reactions are still commented out; feedback only records if the user manually reacts. Revisit now that persistence is solid, if richer feedback signal is wanted.

## Blockers
- None currently known. Open item to verify (not a hard blocker): confirm the DigitalOcean droplet's `DATABASE_PATH` directory exists and is writable by the bot's process user *before* the first deploy, to avoid repeating the local `PermissionError` seen during dev.
