# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is
A Discord bot that posts an AI-curated tech news digest (AI/ML, data science, SWE, general tech). Pipeline: fetch → keyword pre-filter → Claude curates/ranks → Claude summarizes → post embeds to Discord → reactions/buttons feed back into future curation. A 🔖 **Save to Notion** button exports an article to a Notion reading-list database.

## Session workflow
- Start of session read, in order: `README.md`, `docs/HANDOFF.md`, latest entry of `docs/SESSION_LOG.md`, `docs/DECISIONS.md`, `docs/RUNBOOK.md`.
- End of session: update `docs/HANDOFF.md` (`Last updated` as `YYYY-MM-DD HH:MM UTC`, current state, top 3 next actions, blockers), append a timestamped entry to `docs/SESSION_LOG.md`, record durable decisions in `docs/DECISIONS.md`, put operational command changes in `docs/RUNBOOK.md`.
- Stage only explicitly requested files (never `git add -A`); untracked scratch files (`dummy.py`, `hello.py`, `fixes.md`) are not part of the project.
- Ask first before adding dependencies (`uv add` edits `pyproject.toml`) or changing credentials/env vars.
- Add docstrings to new public functions.

## Commands
- `uv sync` — install deps (Python >=3.12)
- `uv run python bot.py` — run the bot locally (needs `.env`, copied from `.env.example`)
- Tests are plain scripts run as modules from the project root (no pytest):
  - `uv run python -m test.test_curator` (ranking tests need `ANTHROPIC_API_KEY`)
  - `uv run python -m test.test_fetcher [tds|arxiv|hn|github|tldr|all]` (needs internet)
  - `uv run python -m test.test_feedback_store`, `test.test_summarizer`, `test.test_notion_client` (hermetic; add `--live` for a real Notion round-trip that creates then archives a page)
  - `uv run python -m test.test_notion_connection` — prints the Notion DB schema (property names/types/options); source of truth for `build_properties()`
- No linter/formatter configured.

## Architecture
- `bot.py` — entry point: discord.py client, APScheduler (`AsyncIOScheduler`, America/Los_Angeles; digest cron currently Mon/Wed/Fri at `DIGEST_HOUR`), slash commands (`/digest`, `/saved`, `/stats`, `/help`), `send_digest()` orchestrates the pipeline, `SaveToNotionView` is the persistent button. One shared aiohttp session is passed to the fetchers and the Notion client. `bot.py` has no automated tests (can't be imported without Discord env vars).
- `agent/news_fetcher.py` — `NewsFetcher` pulls HackerNews, TLDR AI, GitHub Trending, Towards Data Science, ArXiv; shared `HEADERS` User-Agent (TDS 403s without it); dedups against previously sent URLs via `feedback_store.get_sent_urls()`.
- `agent/curator_agent.py` — keyword pre-filter (`interests.json`), then Claude ranks a *candidate pool* (`candidate_pool_size`) and returns `reading_time`; `_balance_selection()` deterministically enforces `max_per_source` and depth mix. Raw Claude responses are logged to `logs/curator/` (gitignored).
- `agent/summarizer_agent.py` — Claude writes a two-part summary; `parse_summary()` splits it into `Technical Summary` / `Why It Matters`.
- `agent/feedback_store.py` — SQLite (`articles` + `reactions`, WAL, 5s busy timeout, idempotent `_migrate_schema()`); maps Discord `message_id` → article. Feeds reaction history back to the curator.
- `agent/notion_client.py` — thin async REST client (no `notion-client` SDK), `Notion-Version: 2022-06-28`. Mapping tables `CATEGORY_TO_NOTION`, `SOURCE_TO_NOTION`, `STATUS_KEY/STATUS_DEFAULT`.
- `interests.json` — keyword lists and thresholds (`max_articles_per_digest`, `candidate_pool_size`, `max_per_source`, `min_relevance_score`, `prefilter_limit`).

## Non-obvious gotchas
- `load_dotenv()` must stay at the top of `bot.py`, before any `agent.*` import: `feedback_store` reads `DATABASE_PATH` at import time. `load_dotenv()` doesn't override already-exported shell vars, so a stray `FEEDBACK_DB_PATH`/`DATABASE_PATH` in the shell silently wins.
- Use absolute `from agent.<module> import ...` imports; bare imports fail (only the project root is on `sys.path`), and a broad `except` previously masked this.
- Python doesn't hot-reload: restart the bot after code changes.
- Save-to-Notion button: one fixed `custom_id`, `timeout=None`, registered via `bot.add_view()` in `setup_hook`; article is recovered from `interaction.message.id` via the `articles` table. The generated summary must be persisted with `register_message(msg.id, article, summary=summary_text)`; the article dict's own `summary` is the source preview, not the generated text. Older messages fall back to the embed description.
- Notion: payload property names/types must match the DB exactly (names in both `build_properties()` and the `url_exists()` filter); unknown select options are auto-created silently, so map new fetcher sources in `SOURCE_TO_NOTION`. Dedup is by `Article Link`.
- A successful Notion save also records a 🔖 reaction for the curator.
- Auto-added 👍👎🔖 reactions in `bot.py` are currently commented out.

## Config / deploy
Env vars: `DISCORD_BOT_TOKEN`, `DISCORD_CHANNEL_ID` (integer), `ANTHROPIC_API_KEY`, `DIGEST_HOUR`, `DATABASE_PATH` (default `./data/feedback.db`; `/data/feedback.db` on the droplet — directory must exist and be writable), `NOTION_TOKEN`, `NOTION_DATABASE_ID` (feature self-disables without the last two). Deployed on a DigitalOcean droplet (Railway previously). See `docs/RUNBOOK.md` for deployment checklists and Notion token rotation; `docs/DECISIONS.md` for rationale behind the above.
