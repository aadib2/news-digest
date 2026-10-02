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
├── data/
│   └── feedback.db             ← Auto-created at runtime (SQLite, persisted on Railway volume)
├── logs/
│   └── curator/                ← Raw Claude responses for debugging (local only)
├── agent/
│   ├── __init__.py
│   ├── news_fetcher.py         ← Fetches from 5+ data sources
│   ├── curator_agent.py        ← Claude ranks articles
│   ├── summarizer_agent.py     ← Claude writes summaries + parse_summary()
│   ├── feedback_store.py       ← Tracks your reactions (upvote/downvote/save) in SQLite
│   └── notion_client.py        ← Saves articles to your Notion reading list
├── test/
│   ├── test_curator.py         ← Unit tests for curator JSON extraction
│   ├── test_fetcher.py         ← Tests for news fetching
│   ├── test_feedback_store.py  ← Unit tests for feedback store
│   ├── test_summarizer.py      ← Unit tests for summary parsing
│   ├── test_notion_client.py   ← Unit tests for the Notion payload/client
│   └── test_notion_connection.py ← Prints your Notion DB schema (property names + types)
└──
```

---

## How does it work?

1. **Fetch** — Pulls articles from multiple sources (HackerNews, TLDR, GitHub Trending, Towards Data Science, Reddit) via `NewsFetcher`
2. **Pre-filter** — Heuristically scores articles using your `high_interest_keywords` / `low_interest_keywords` to reduce token usage (~25 articles)
3. **Curate** — Sends pre-filtered articles to Claude with your interest profile; Claude returns top 8 ranked by relevance score and taking into account reading diversity.
4. **Summarize** — For each selected article, Claude generates a concise 2-3 sentence summary
5. **Post** — Bot sends formatted embeds to Discord with 👍 👎 🔖 reactions and a **Save to Notion** button
6. **Learn** — Your reactions are stored and fed back to the curator as feedback context for future digests
7. **Save** — Clicking **Save to Notion** writes the article (title, link, source, category, both summary halves) to your Notion reading list with status `To Read`

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

### Step 4: Connect Your Notion Reading List

Required for the **Save to Notion** button (the bot runs fine without it — the button just reports that Notion isn't configured).

1. Go to https://www.notion.so/my-integrations → **New integration** → name it (e.g. "news-digest") → submit
2. Copy the **Internal Integration Secret** → this is your `NOTION_TOKEN`
3. Open your reading-list database in Notion → **⋯** menu → **Connections** → add your integration
4. Copy the database ID from its URL (the 32-char hex before `?v=`) → this is your `NOTION_DATABASE_ID`
5. Verify the integration can see your schema:
   ```bash
   uv run python -m test.test_notion_connection
   ```
   This prints every property name, type, and select option. **The payload in `agent/notion_client.py` must match this output exactly** — names are case- and space-sensitive, and types are validated by Notion (see Troubleshooting).

Properties the bot writes: `Title` (title), `Article Link` (url), `Source` (select), `Category` (select), `Technical Summary` (rich_text), `Why It Matters` (rich_text), `Date Added` (date), `Status` (select → `To Read`). `Key Takeaways`, `Subcategories`, and `Date Read` are left for you to fill in.

---

### Step 5: Configure Environment

```bash
cp .env.example .env
```

Edit `.env`:
```
DISCORD_BOT_TOKEN=your_bot_token_here
DISCORD_CHANNEL_ID=your_channel_id_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here
DIGEST_HOUR=8
DATABASE_PATH=./data/feedback.db     # SQLite path (droplet: /data/feedback.db)
NOTION_TOKEN=your_notion_secret_here
NOTION_DATABASE_ID=your_database_id_here
```

> **ANTHROPIC_API_KEY**: Get yours at https://console.anthropic.com

---

### Step 6: Run Locally

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

### Step 7: Deploy (So It Runs 24/7)

#### Option A: Railway (Recommended, free tier)
1. Push to GitHub
2. Go to https://railway.app → New Project → Deploy from GitHub
3. Add environment variables in Railway dashboard (including `NOTION_TOKEN` / `NOTION_DATABASE_ID` if you want the Save button)
4. **Add a Railway Volume**: Project → Service → Volumes → Add Volume → Mount Path: `/data`
5. Set `DATABASE_PATH=/data/feedback.db` in Railway Variables
6. Done — Railway keeps it always on

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

### Buttons
| Button | What it does |
|--------|--------------|
| 🔖 **Save to Notion** | Creates a page in your Notion reading list with the article's metadata and both summary halves, sets `Status = To Read`, and records a 🔖 for the curator. The button then shows **Saved ✓**. |

> The button is a *persistent* component — it keeps working on old digest messages across bot restarts. Clicking an article that's already in Notion reports "Already in your Notion reading list ✓" instead of creating a duplicate (matched on the `Article Link` URL).

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
  "candidate_pool_size": 20,
  "max_per_source": 3,
  "min_relevance_score": 55,
  "prefilter_limit": 25
}
```

| Setting | Description |
|---------|-------------|
| `high_interest_keywords` | Boost articles containing these terms |
| `low_interest_keywords` | Penalize articles containing these terms |
| `max_articles_per_digest` | Max articles to show per digest (default 8) |
| `candidate_pool_size` | How many articles to ask Claude to rank (default 20) |
| `max_per_source` | Max articles from any single source in final digest (default 3) |
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

**Save button says "Notion isn't configured"**
- `NOTION_TOKEN` / `NOTION_DATABASE_ID` missing from the environment — set them and restart the bot

**Notion 400: `"X is expected to be select"` (or `rich_text`, `date`, …)**
- The payload type in `agent/notion_client.py` doesn't match that property's type in your database
- Run `uv run python -m test.test_notion_connection` and align `build_properties()` with the printed types

**Notion 400: `"Could not find property with name or id: X"`**
- A property name mismatch (names are case- and space-sensitive, e.g. `Article Link` vs `ArticleLink`)
- Fix the name in **both** `build_properties()` and the `url_exists()` filter

**Duplicate options appearing in a Notion select**
- Notion auto-creates a select option when you send a name that doesn't exist yet
- The bot's source strings (e.g. `HackerNews`, `Towards Data Science`) must match your `Source` options (e.g. `Hacker News`, `TDS`) or you'll get near-duplicates — map them in `agent/notion_client.py`

**Technical Summary / Why It Matters are blank in Notion**
- The generated summary must be persisted at digest time: `register_message(msg.id, article, summary=summary_text)` in `bot.py`
- Articles posted before that column existed fall back to the Discord embed's description at click time
