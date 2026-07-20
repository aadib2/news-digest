"""
bot.py
Main entry point for the Tech Digest Discord bot.

Features:
  - Sends a curated daily digest at configurable time
  - Tracks 👍 👎 🔖 reactions per article
  - Slash commands: /digest, /saved, /stats, /help
  - APScheduler for reliable daily scheduling
"""
from dotenv import load_dotenv
load_dotenv()

import asyncio
import json
import os
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

import agent.feedback_store as feedback_store
from agent.news_fetcher import NewsFetcher
from agent.curator_agent import CuratorAgent
from agent.summarizer_agent import SummarizerAgent
import aiohttp

# ─────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────
DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID"))
DIGEST_HOUR = int(os.getenv("DIGEST_HOUR", "8"))

with open("interests.json") as f:
    INTERESTS = json.load(f)

# ─────────────────────────────────────────────
# Category colours & emojis for Discord embeds
# ─────────────────────────────────────────────
CATEGORY_META = {
    "machine_learning / AI":  {"emoji": "🤖", "color": discord.Color.purple()},
    "data_science":      {"emoji": "📊", "color": discord.Color.blue()},
    "software_engineering":  {"emoji": "⚙️",  "color": discord.Color.orange()},
    "general_tech":      {"emoji": "💡", "color": discord.Color.green()},
}
DEFAULT_META = {"emoji": "📰", "color": discord.Color.greyple()}


# ─────────────────────────────────────────────
# Bot setup
# ─────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree   # Slash command tree

fetcher = NewsFetcher()
curator = CuratorAgent(INTERESTS)
summarizer = SummarizerAgent()
scheduler = AsyncIOScheduler(timezone="America/Los_Angeles")


# Shared aiohttp session (created on ready)
aiohttp_session = None


async def _close_aiohttp_session():
    """Properly close the shared aiohttp session."""
    global aiohttp_session
    if aiohttp_session is not None and not aiohttp_session.closed:
        await aiohttp_session.close()
        print("[Bot] Closed shared aiohttp session")


@bot.event
async def on_close():
    """Called when the bot is shutting down."""
    await _close_aiohttp_session()
    scheduler.shutdown(wait=False)
    print("[Bot] Scheduler shut down")


# ─────────────────────────────────────────────
# Core: build and send the digest
# ─────────────────────────────────────────────
async def send_digest(channel: discord.TextChannel):
    """Fetch → curate → summarize → post."""

    # Header
    header_embed = discord.Embed(
        title="📰 Tech News Digest",
        description=(
            "Your daily curated digest across **AI/ML**, **Data Science**, "
            "**Software Engineering**, and **General Tech**.\n\n"
            "React with 👍 upvote · 👎 downvote · 🔖 save"
        ),
        color=discord.Color.gold(),
        timestamp=datetime.now(timezone.utc),
    )
    header_embed.set_footer(text=f"Powered by Claude · {datetime.now().strftime('%A, %B %-d %Y')}")
    await channel.send(embed=header_embed)

    # Fetch
    await channel.send("⏳ Fetching articles...", delete_after=10)
    articles = await fetcher.fetch_all(session=aiohttp_session)

    if not articles:
        await channel.send("⚠️ No articles fetched today. Check source connectivity.")
        return

    # Curate
    feedback_summary = feedback_store.get_summary()
    curated = await curator.rank_articles(articles, feedback_summary)

    if not curated:
        await channel.send("⚠️ No articles passed the relevance threshold today.")
        return

    # Summarize & post each article
    for i, article in enumerate(curated, start=1):
        meta = CATEGORY_META.get(article.get("category", ""), DEFAULT_META)

        summary_text = await summarizer.summarize(article)

        embed = discord.Embed(
            title=f"{meta['emoji']} {article['title'][:200]}",
            url=article["url"],
            description=summary_text,
            color=meta["color"],
        )
        embed.add_field(
            name="Source",
            value=article["source"],
            inline=True,
        )
        embed.add_field(
            name="Category",
            value=article.get("category", "—").replace("_", " ").title(),
            inline=True,
        )
        embed.add_field(
            name="Relevance",
            value=f"{article.get('relevance_score', '—')}/100",
            inline=True,
        )
        embed.set_footer(text=f"Article {i} of {len(curated)}")

        msg = await channel.send(embed=embed)

        # Bot add reaction buttons (unnecessary now)
        # for emoji in ("👍", "👎", "🔖"):
        #     await msg.add_reaction(emoji)

        # Store message → article mapping for feedback tracking
        feedback_store.register_message(msg.id, article)

        await asyncio.sleep(0.5)  # Avoid rate limiting

    # Footer summary
    footer_embed = discord.Embed(
        description=f"✅ **Digest complete** — {len(curated)} articles curated from {len(articles)} fetched.",
        color=discord.Color.dark_grey(),
    )
    await channel.send(embed=footer_embed)
    print(f"[Bot] Digest sent at {datetime.now().isoformat()}")


# ─────────────────────────────────────────────
# Bot events
# ─────────────────────────────────────────────
@bot.event
async def on_ready():
    print(f"[Bot] Logged in as {bot.user} (ID: {bot.user.id})")

    # Sync slash commands
    await tree.sync()
    print("[Bot] Slash commands synced")

    # Schedule daily digest
    scheduler.add_job(
        _scheduled_digest,
        CronTrigger(day_of_week='mon-fri', hour=DIGEST_HOUR, minute=0, timezone=scheduler.timezone),
        id="daily_digest",
        replace_existing=True,
    )
    scheduler.start()
    print(f"[Bot] Scheduler started → daily digest at {DIGEST_HOUR:02d}:00")
    # Create shared aiohttp session
    global aiohttp_session
    if aiohttp_session is None:
        connector = aiohttp.TCPConnector(limit=20)
        aiohttp_session = aiohttp.ClientSession(connector=connector)
        print("[Bot] Created shared aiohttp session")


async def _scheduled_digest():
    """Wrapper for the scheduler to call."""
    channel = bot.get_channel(CHANNEL_ID)
    if channel:
        await send_digest(channel)
    else:
        print("[Bot] Scheduled digest failed: channel not found")


@bot.event
async def on_reaction_add(reaction: discord.Reaction, user: discord.User):
    """Track reactions to digest articles."""
    if user.bot:
        return   # Ignore bot's own initial reactions

    emoji = str(reaction.emoji)
    if emoji in ("👍", "👎", "🔖"):
        feedback_store.record_reaction(reaction.message.id, emoji)
        print(f"[Feedback] {user.name} reacted {emoji} to message {reaction.message.id}")


# ─────────────────────────────────────────────
# Slash commands
# ─────────────────────────────────────────────
@tree.command(name="digest", description="Trigger today's tech news digest manually")
async def slash_digest(interaction: discord.Interaction):
    await interaction.response.send_message("⏳ Generating digest...", ephemeral=True)
    channel = bot.get_channel(CHANNEL_ID)
    if channel:
        await send_digest(channel)
    else:
        await interaction.followup.send("❌ Digest channel not found.", ephemeral=True)


@tree.command(name="saved", description="Show your saved (🔖) articles")
async def slash_saved(interaction: discord.Interaction):
    saved = feedback_store.get_saved_articles()
    if not saved:
        await interaction.response.send_message(
            "No saved articles yet. React with 🔖 to save articles from the digest.",
            ephemeral=True,
        )
        return

    embed = discord.Embed(
        title="🔖 Your Saved Articles",
        color=discord.Color.teal(),
        timestamp=datetime.now(timezone.utc),
    )
    for i, article in enumerate(saved[-10:], start=1):  # Show last 10
        embed.add_field(
            name=f"{i}. {article['title'][:80]}",
            value=f"[Read →]({article['url']}) · {article['source']}",
            inline=False,
        )

    await interaction.response.send_message(embed=embed, ephemeral=True)


@tree.command(name="stats", description="View your engagement stats and top topics")
async def slash_stats(interaction: discord.Interaction):
    summary = feedback_store.get_summary()

    embed = discord.Embed(
        title="📊 Your Digest Engagement Stats",
        color=discord.Color.blue(),
        timestamp=datetime.now(timezone.utc),
    )
    embed.add_field(name="👍 Upvoted", value=str(summary["upvoted_count"]), inline=True)
    embed.add_field(name="👎 Downvoted", value=str(summary["downvoted_count"]), inline=True)
    embed.add_field(name="🔖 Saved", value=str(summary["saved_count"]), inline=True)
    embed.add_field(
        name="Engagement Rate",
        value=f"{summary['engagement_rate'] * 100:.0f}%",
        inline=True,
    )
    embed.add_field(
        name="Top Topics",
        value=", ".join(summary["top_topics"]) if summary["top_topics"] else "Not enough data yet",
        inline=False,
    )
    embed.add_field(
        name="Top Sources",
        value=", ".join(summary["top_sources"]) if summary["top_sources"] else "Not enough data yet",
        inline=False,
    )
    embed.set_footer(text="Feedback is used to tune future digests 🤖")

    await interaction.response.send_message(embed=embed, ephemeral=True)


@tree.command(name="help", description="Show available bot commands")
async def slash_help(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🤖 Tech Digest Bot — Commands",
        color=discord.Color.gold(),
    )
    embed.add_field(
        name="/digest",
        value="Manually trigger today's digest",
        inline=False,
    )
    embed.add_field(
        name="/saved",
        value="View articles you've bookmarked with 🔖",
        inline=False,
    )
    embed.add_field(
        name="/stats",
        value="See your engagement stats and top interests",
        inline=False,
    )
    embed.add_field(
        name="Reactions",
        value="👍 upvote  ·  👎 downvote  ·  🔖 save\nReactions help the bot learn your preferences over time.",
        inline=False,
    )
    embed.set_footer(text=f"Digest sent daily at {DIGEST_HOUR:02d}:00 AM PT")
    await interaction.response.send_message(embed=embed, ephemeral=True)


# ─────────────────────────────────────────────
# Run
# ─────────────────────────────────────────────
if __name__ == "__main__":
    if not DISCORD_TOKEN:
        raise ValueError("DISCORD_BOT_TOKEN is not set in .env")
    if not CHANNEL_ID:
        raise ValueError("DISCORD_CHANNEL_ID is not set in .env")

    bot.run(DISCORD_TOKEN)
