"""
notion_client.py
Thin async client for the Notion REST API. Creates reading-list pages
from digest articles using the bot's shared aiohttp session.
"""

import os
from datetime import datetime, timezone
import aiohttp

from agent.summarizer_agent import parse_summary

NOTION_API_BASE = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"

# Bot categories → Notion Category options (from Task 1's inspection)
CATEGORY_TO_NOTION = {
    "machine_learning / AI": "ML/AI",
    "data_science": "Data Science",
    "software_engineering": "SWE",
    "general_tech": "General Tech",
}
STATUS_KEY = "select" 
STATUS_DEFAULT = "To Read"

class NotionNotConfigured(RuntimeError):
    """Raised when NOTION_TOKEN or NOTION_DATABASE_ID is not set."""

def config():
    """Return (token, database_id) or raise NotionNotConfigured."""
    token = os.getenv("NOTION_TOKEN")
    database_id = os.getenv("NOTION_DATABASE_ID")
    if not token or not database_id:
        raise NotionNotConfigured("Set NOTION_TOKEN and NOTION_DATABASE_ID in .env")
    return token, database_id

def headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }

def build_properties(article: dict) -> dict:
    """Build the Notion page "properties" payload for a given article"""

    technical, why_it_matters = parse_summary(article.get("summary", "")) # grab summary from summarizer agent
    props = {
        "Title": {"title": [{"text": {"content": article.get("title", "")[:2000]}}]},
        "Article Link": {"url": article.get("url", "")},
        "Source": {"rich_text": [{"text": {"content": article.get("source", "")}}]},
        "Technical Summary": {"rich_text": [{"text": {"content": technical[:2000]}}]},
        "Why It Matters": {"rich_text": [{"text": {"content": why_it_matters[:2000]}}]},
        "Date Added": {"date": {"start": datetime.now(timezone.utc).isoformat()}},
        "Status": {STATUS_KEY: {"name": STATUS_DEFAULT}}, # assign "To Read" default
    }
    category = CATEGORY_TO_NOTION.get(article.get("category", ""), "") # map category to the one notion expects
    if category:
        props["Category"] = {"select": {"name": category}}
    return props

"""
notion_client.py
Thin async client for the Notion REST API. Creates reading-list pages
from digest articles using the bot's shared aiohttp session.
"""

import os
from datetime import datetime, timezone

import aiohttp

from agent.summarizer_agent import parse_summary

NOTION_API_BASE = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"

# Bot categories → Notion Category options (from Task 1's inspection)
CATEGORY_TO_NOTION = {
    "machine_learning / AI": "ML/AI",
    "data_science": "Data Science",
    "software_engineering": "SWE",
    "general_tech": "General Tech",
}
STATUS_KEY = "status"  # "status" or "select" — from Task 1's inspection
STATUS_DEFAULT = "to read"


class NotionNotConfigured(RuntimeError):
    """Raised when NOTION_TOKEN or NOTION_DATABASE_ID is not set."""


def config():
    """Return (token, database_id) or raise NotionNotConfigured."""
    token = os.getenv("NOTION_TOKEN")
    database_id = os.getenv("NOTION_DATABASE_ID")
    if not token or not database_id:
        raise NotionNotConfigured("Set NOTION_TOKEN and NOTION_DATABASE_ID in .env")
    return token, database_id


def headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


def build_properties(article: dict) -> dict:
    """Build the Notion page `properties` payload for a digest article."""
    technical, why_it_matters = parse_summary(article.get("summary", ""))
    props = {
        "Title": {"title": [{"text": {"content": article.get("title", "")[:2000]}}]},
        "Article Link": {"url": article.get("url", "")},
        "Source": {"rich_text": [{"text": {"content": article.get("source", "")}}]},
        "Technical Summary": {"rich_text": [{"text": {"content": technical[:2000]}}]},
        "Why It Matters": {"rich_text": [{"text": {"content": why_it_matters[:2000]}}]},
        "Date Added": {"date": {"start": datetime.now(timezone.utc).isoformat()}},
        "Status": {STATUS_KEY: {"name": STATUS_DEFAULT}},
    }
    category = CATEGORY_TO_NOTION.get(article.get("category", ""), "")
    if category:
        props["Category"] = {"select": {"name": category}}
    return props


async def create_reading_entry(session: aiohttp.ClientSession, article: dict) -> dict:
    """Create a page in the reading-list database. Returns the created page JSON."""
    token, database_id = config()
    payload = {"parent": {"database_id": database_id}, "properties": build_properties(article)}
    async with session.post(
        f"{NOTION_API_BASE}/pages", json=payload, headers=headers(token)
    ) as resp:
        if resp.status != 200:
            body = await resp.text()
            raise RuntimeError(f"Notion create failed ({resp.status}): {body[:300]}")
        return await resp.json()


async def url_exists(session: aiohttp.ClientSession, url: str) -> bool:
    """True if a reading-list page already has this URL (duplicate check)."""
    if not url:
        return False
    token, database_id = config()
    payload = {
        "filter": {"property": "Article Link", "url": {"equals": url}},
        "page_size": 1,
    }
    async with session.post(
        f"{NOTION_API_BASE}/databases/{database_id}/query",
        json=payload,
        headers=headers(token),
    ) as resp:
        if resp.status != 200:
            body = await resp.text()
            raise RuntimeError(f"Notion query failed ({resp.status}): {body[:300]}")
        data = await resp.json()
    return bool(data.get("results"))
