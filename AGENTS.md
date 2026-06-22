# AGENTS.md

## Project Overview
A daily AI-curated tech news Discord bot using Claude for content ranking and summarization.

## Entry Points
- **Main**: `bot.py` - Discord bot with scheduler
- **Core**: `agent/news_fetcher.py` - Fetches from 5+ sources (TDS, ArXiv, HN, GitHub Trending, TLDR AI)
- **AI**: `agent/curator_agent.py` - Claude ranks articles
- **AI**: `agent/summarizer_agent.py` - Claude writes summaries

## Developer Commands

### Setup & Run
- `uv sync` - Install deps (recommended)
- OR `python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`
- `uv run python bot.py` - Run bot locally
- OR `python bot.py`

### Test
- `python -m test/test_curator.py` - Test curator agent. Run in project root
- `python -m test/test_fetcher.py [tds|arxiv|hn|github|tldr|all]` - Test fetcher (single or all). Also run in project root.

## Environment
Create `.env` from `.env.example`:
```
DISCORD_BOT_TOKEN=your_token
DISCORD_CHANNEL_ID=your_channel_id  
ANTHROPIC_API_KEY=your_anthropic_key
DIGEST_HOUR=8  # PT (default)
```

## Test Requirements
- `test_curator.py` needs `ANTHROPIC_API_KEY` for ranking tests
- `test_fetcher.py` needs internet connection
- All tests run with Python 3.12+

## Key Config
- `interests.json` - Your keyword filters and thresholds
- `feedback.json` - Tracks reaction history
- `requirements.txt` - Dependencies

## Architecture Notes
- Monolithic single-package structure
- aiohttp session pooling for efficiency
- APScheduler handles daily digests
- Claude integrated via anthropic API (sync/async)
- Clean separation: fetch → curate → summarize → post

## Debugging
- `logs/curator/` - Raw Claude responses
- Set `DIGEST_HOUR` for different schedule
- Lower `min_relevance_score` in `interests.json` to include more articles
- Check network if all fetchers fail

## Deploy
- **Railway** - This is project is deployed on Railway so bot always stays active.
