# Tech Digest Bot

A daily AI-curated tech news Discord bot, filtered for AI/ML, Data Science, Software Engineering, and General Tech.

---

## Project Structure

```
news-digest/
├── bot.py                      ← Main entry point (Discord bot + scheduler)
├── interests.json              ← Your interest profile (tweak anytime)
├── requirements.txt            ← Python dependencies
├── .env.example                ← Copy to .env and fill in
├── feedback.json               ← Auto-created at runtime (reaction tracking)
├── logs/
│   └── curator/                ← Raw Claude responses for debugging (local only)
├── agent/
│   ├── __init__.py
│   ├── news_fetcher.py         ← Fetches from 5+ data sources
│   ├── curator_agent.py        ← Claude ranks articles by relevance
│   ├── summarizer_agent.py     ← Claude writes concise summaries
│   └── feedback_store.py       ← Tracks your reactions (upvote/downvote/save)
├── test/
│   ├── test_curator.py         ← Unit tests for curator JSON extraction
│   └── test_fetcher.py         ← Tests for news fetching

```

---

## How does it work?

1. **Fetch** — Pulls articles from multiple sources (HackerNews, TLDR, GitHub Trending, Towards Data Science, Reddit) via `NewsFetcher`
2. **Pre-filter** — Heuristically scores articles using your `high_interest_keywords` / `low_interest_keywords` to reduce token usage (~25 articles)
3. **Curate** — Sends pre-filtered articles to Claude with your interest profile; Claude returns top 8 ranked by relevance score
4. **Summarize** — For each selected article, Claude generates a concise 2-3 sentence summary
5. **Post** — Bot sends formatted embeds to Discord with 👍 👎 🔖 reactions
6. **Learn** — Your reactions are stored and fed back to the curator as feedback context for future digests

## Architecture Diagram

<img src="News-Digest Agent.drawio.png" alt="Pipeline Diagram" width="300" />

---

## Setup Instructions

### Step 1: Clone & Install

```bash
# Using uv (recommended)
git clone https://github.com/aadib2/news-digest.git
cd news-digest
uv sync

# Or with pip
git clone https://github.com/aadib2/news-digest.git
cd news-digest
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

---

### Step 2: Create Discord Bot

1. Go to https://discord.com/developers/applications
2. Click **New Application** → name it (e.g. "TechDigest")
3. Go to **Bot** tab → click **Add Bot**
4. Under **Privileged Gateway Intents**, enable:
   - ✅ Message Content Intent
   - ✅ Server Members Intent (optional)
5. Copy the **Bot Token** — you'll need it for `.env`
6. Go to **OAuth2 → URL Generator**:
   - Scopes: `bot`, `applications.commands`
   - Bot Permissions: `Send Messages`, `Embed Links`, `Add Reactions`, `Read Message History`
7. Open the generated URL in your browser → invite bot to your server

---

### Step 3: Get Your Channel ID

1. In Discord, go to **User Settings → Advanced → Enable Developer Mode**
2. Right-click the channel you want digests sent to
3. Click **Copy ID**

---

### Step 4: Configure Environment

```bash
cp .env.example .env
```

Edit `.env`:
```
DISCORD_BOT_TOKEN=your_bot_token_here
DISCORD_CHANNEL_ID=your_channel_id_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here
DIGEST_HOUR=8
```

> **ANTHROPIC_API_KEY**: Get yours at https://console.anthropic.com

---

### Step 5: Run Locally

```bash
# With uv
uv run python bot.py

# Or with pip
python bot.py
```

You'll see:
```
[Bot] Logged in as TechDigest#1234 (ID: ...)
[Bot] Slash commands synced
[Bot] Scheduler started → daily digest at 08:00
```

**Test immediately** with the `/digest` slash command in Discord.

---

### Step 6: Deploy (So It Runs 24/7)

#### Option A: Railway (Recommended, free tier)
1. Push to GitHub
2. Go to https://railway.app → New Project → Deploy from GitHub
3. Add environment variables in Railway dashboard
4. Done — Railway keeps it always on

#### Option B: Replit
1. Create a new Python Repl
2. Upload all files
3. Add Secrets (equivalent of `.env`)
4. Run `python bot.py`
5. Enable "Always On" (Replit paid feature) or use UptimeRobot

#### Option C: Your Own Machine
- Windows: Use Task Scheduler or run in background with `pythonw bot.py`
- Linux/Mac: Use `screen` or `tmux`: `screen -S digest python bot.py`

---

## Usage

| Command | Description |
|---------|-------------|
| `/digest` | Trigger today's digest manually |
| `/saved` | View your 🔖 bookmarked articles |
| `/stats` | See your engagement stats + top topics |
| `/help` | Show all commands |

### Reactions
| Emoji | Meaning |
|-------|---------|
| 👍 | Upvote — more like this |
| 👎 | Downvote — less like this |
| 🔖 | Save — add to your reading list |

> Reactions are tracked and passed to the curator so future digests improve over time.

---

## Customising Your Interests

Edit `interests.json` to tune what the curator prioritises.

```json
{
  "high_interest_keywords": [
    "LLM", "RAG", "finetuning", "transformer", "attention", ...
  ],
  "low_interest_keywords": [
    "crypto", "blockchain", "web3", "NFT", ...
  ],
  "max_articles_per_digest": 8,
  "min_relevance_score": 55,
  "prefilter_limit": 25
}
```

| Setting | Description |
|---------|-------------|
| `high_interest_keywords` | Boost articles containing these terms |
| `low_interest_keywords` | Penalize articles containing these terms |
| `max_articles_per_digest` | Max articles to show per digest (default 8) |
| `min_relevance_score` | Minimum score to include (0-100, default 55) |
| `prefilter_limit` | Articles sent to Claude after keyword filtering (default 25) |

---

## Troubleshooting

**Bot doesn't respond to `/digest`**
- Make sure slash commands synced — restart the bot and wait ~1 min

**"Channel not found" error**
- Double check `DISCORD_CHANNEL_ID` in `.env` — must be an integer, no quotes

**Claude returns no articles**
- Lower `min_relevance_score` in `interests.json` (try 40)
- Check your `ANTHROPIC_API_KEY` is valid

**GitHub Trending returns nothing**
- These occasionally go down; other sources will still work
- Check your internet connection if all sources fail

**JSON parse errors in curator**
- Check `logs/curator/` for raw Claude responses
- Usually caused by token truncation — reduce `prefilter_limit` or increase `max_tokens` in curator_agent.py
