# AGENTS.md

## Session Start

Read in this exact order:
1. `README.md`
2. `docs/HANDOFF.md`
3. latest entry in `docs/SESSION_LOG.md`
4. `docs/DECISIONS.md`
5. `docs/RUNBOOK.md`

## During Work

- Keep `docs/HANDOFF.md` aligned with current status and next actions.
- Record durable decisions in `docs/DECISIONS.md`.
- Keep operational command changes in `docs/RUNBOOK.md`.

## Session End

- Update `docs/HANDOFF.md`:
  - `Last updated` timestamp (`YYYY-MM-DD HH:MM UTC`)
  - current state
  - top 3 next actions
  - blockers (if any)
- Append a new timestamped entry to `docs/SESSION_LOG.md`.
- Confirm no secrets were added to tracked files.


## Project Overview
A daily AI-curated tech news Discord bot using Claude for content ranking and summarization.

## Architecture Notes
- Monolithic single-package structure
- aiohttp session pooling for efficiency
- APScheduler handles daily digests
- Claude integrated via anthropic API (sync/async)
- Clean separation: fetch → curate → summarize → post

## Entry Points
- **Main**: `bot.py` - Discord bot with scheduler
- **Core**: `agent/news_fetcher.py` - Fetches from 5+ sources (TDS, ArXiv, HN, GitHub Trending, TLDR AI)
- **AI**: `agent/curator_agent.py` - Claude ranks articles
- **AI**: `agent/summarizer_agent.py` - Claude writes summaries

## Always Do
- Add docstrings to new public functions
- Stage only explicitly requested files (never git add -A)

## Ask first
- Updating external API credentials or environment variables
- Adding new dependencies with `uv add <name>` which updates `pyproject.toml`

## Developer Commands

### Setup & Run
- `uv sync` - Install deps (recommended)
- OR `python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`
- `uv run python bot.py` - Run bot locally
- OR `python3 bot.py`

### Tests
- `python3 -m test/test_curator.py` - Test curator agent. Run in project root. Needs `ANTHROPIC_API_KEY` for ranking tests.
- `python3 -m test/test_fetcher.py [tds|arxiv|hn|github|tldr|all]` - Test fetcher (single or all). Also run in project root. Requires internet connection.
- All tests run with Python 3.12+

## Environment
Create `.env` from `.env.example`:
```
DISCORD_BOT_TOKEN=your_token
DISCORD_CHANNEL_ID=your_channel_id  
ANTHROPIC_API_KEY=your_anthropic_key
DIGEST_HOUR=8  # PT (default)
```

## Key Config
- `interests.json` - Your keyword filters and thresholds
- `feedback.json` - Tracks reaction history
- `requirements.txt` - Dependencies

## Deploy
- **Railway** - This is project is deployed on Railway so bot always stays active. It uses a Railway Volume for the
`data` directory, making the `feedback.json` persistent across digests.
