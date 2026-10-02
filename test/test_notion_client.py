"""
test_notion_client.py
Unit tests for the Notion client (mocked aiohttp) + optional live round-trip.
Run: uv run python -m test.test_notion_client
Add --live to also run a round-trip against your real Notion database
(uses NOTION_TOKEN/NOTION_DATABASE_ID from .env).
"""

import os
import sys

# Hard-set test credentials so exported shell variables can't leak into unit tests
os.environ["NOTION_TOKEN"] = "secret_test_token"
os.environ["NOTION_DATABASE_ID"] = "0" * 32

import aiohttp

from agent.notion_client import (
    NotionNotConfigured, build_properties, create_reading_entry, url_exists,
)
from agent.summarizer_agent import parse_summary

ARTICLE = {
    "title": "Linear Attention Is All You Need",
    "url": "https://example.com/linear-attention",
    "source": "HackerNews",
    "category": "machine_learning / AI",
    "relevance_score": 92,
    "summary": "Technical Summary\n\nLinear attention runs in O(n).\n\n**Why it matters:** Cheaper inference.",
}


class FakeResponse:
    def __init__(self, status=200, json_data=None, text_data=""):
        self.status = status
        self._json = json_data or {}
        self._text = text_data

    async def json(self):
        return self._json

    async def text(self):
        return self._text

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


class FakeSession:
    """Stand-in for aiohttp.ClientSession that records calls."""
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def post(self, url, json=None, headers=None):
        self.calls.append({"url": url, "json": json, "headers": headers})
        return self.responses.pop(0)


def test_build_properties():
    props = build_properties(ARTICLE)
    assert props["Title"]["title"][0]["text"]["content"] == ARTICLE["title"]
    assert props["Article Link"]["url"] == ARTICLE["url"]
    assert props["Source"]["select"]["name"] == "Hacker News"
    assert props["Category"]["select"]["name"] == "ML/AI"
    assert props["Technical Summary"]["rich_text"][0]["text"]["content"] == "Linear attention runs in O(n)."
    assert props["Why It Matters"]["rich_text"][0]["text"]["content"] == "Cheaper inference."
    assert props["Status"]["select"]["name"] == "To Read"
    assert props["Date Added"]["date"]["start"]
    print("✅ test_build_properties passed")


def test_build_properties_unknown_category_omits_key():
    article = dict(ARTICLE, category="")
    assert "Category" not in build_properties(article)
    print("✅ test_build_properties_unknown_category_omits_key passed")


def test_build_properties_unmapped_source_omits_key():
    article = dict(ARTICLE, source="Some New Source")
    assert "Source" not in build_properties(article)
    print("✅ test_build_properties_unmapped_source_omits_key passed")


def test_create_reading_entry_sends_correct_request():
    session = FakeSession(FakeResponse(200, {"id": "page-1", "url": "https://notion.so/page-1"}))
    import asyncio
    page = asyncio.run(create_reading_entry(session, ARTICLE))
    call = session.calls[0]
    assert call["url"] == "https://api.notion.com/v1/pages"
    assert call["json"]["parent"] == {"database_id": "0" * 32}
    assert call["json"]["properties"]["Article Link"]["url"] == ARTICLE["url"]
    assert call["headers"]["Notion-Version"] == "2022-06-28"
    assert call["headers"]["Authorization"] == "Bearer secret_test_token"
    assert page["id"] == "page-1"
    print("✅ test_create_reading_entry_sends_correct_request passed")


def test_create_reading_entry_raises_on_error():
    session = FakeSession(FakeResponse(400, text_data='{"message": "Property Title not found"}'))
    import asyncio
    try:
        asyncio.run(create_reading_entry(session, ARTICLE))
        assert False, "should have raised"
    except RuntimeError as e:
        assert "400" in str(e) and "Title not found" in str(e)
    print("✅ test_create_reading_entry_raises_on_error passed")


def test_url_exists():
    session = FakeSession(FakeResponse(200, {"results": [{"id": "existing"}]}))
    assert asyncio_run(url_exists(session, ARTICLE["url"])) is True
    q = session.calls[0]["json"]
    assert q["filter"] == {"property": "Article Link", "url": {"equals": ARTICLE["url"]}}

    session2 = FakeSession(FakeResponse(200, {"results": []}))
    assert asyncio_run(url_exists(session2, "https://new.example.com")) is False
    print("✅ test_url_exists passed")


def asyncio_run(coro):
    import asyncio
    return asyncio.run(coro)


def test_not_configured():
    token, db = os.environ.pop("NOTION_TOKEN"), os.environ.pop("NOTION_DATABASE_ID")
    try:
        import asyncio
        asyncio.run(url_exists(FakeSession(), "https://x.example.com"))
        assert False, "should have raised"
    except NotionNotConfigured:
        pass
    finally:
        os.environ["NOTION_TOKEN"], os.environ["NOTION_DATABASE_ID"] = token, db
    print("✅ test_not_configured passed")


def live_round_trip():
    """Creates a clearly-marked test page, checks dedup, then archives it."""
    import asyncio
    from dotenv import load_dotenv
    load_dotenv(override=True)  # replace the hard-set test creds with the real ones

    async def run():
        async with aiohttp.ClientSession() as s:
            article = dict(ARTICLE, url="https://example.com/news-digest-test")
            page = await create_reading_entry(s, article)
            print(f"  created page: {page['url']}")
            assert await url_exists(s, article["url"]) is True, "dedup check should find it"
            async with s.patch(
                f"https://api.notion.com/v1/pages/{page['id']}",
                json={"archived": True},
                headers={
                    "Authorization": f"Bearer {os.environ['NOTION_TOKEN']}",
                    "Notion-Version": "2022-06-28",
                },
            ) as r:
                assert r.status == 200, await r.text()
            assert await url_exists(s, article["url"]) is False, "archived page should not match"

    asyncio.run(run())
    print("✅ live_round_trip passed")


if __name__ == "__main__":
    test_build_properties()
    test_build_properties_unknown_category_omits_key()
    test_build_properties_unmapped_source_omits_key()
    test_create_reading_entry_sends_correct_request()
    test_create_reading_entry_raises_on_error()
    test_url_exists()
    test_not_configured()
    print("\n🎉 All notion_client tests passed!")
    if "--live" in sys.argv:
        print("\n— Live round-trip (real Notion) —")
        live_round_trip()
