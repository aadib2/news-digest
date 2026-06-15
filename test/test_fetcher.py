# ─────────────────────────────────────────────
# Testing for news fetcher
# ─────────────────────────────────────────────

from agent.news_fetcher import (
    TowardsDataScienceFetcher,
    ArxivFetcher,
    GitHubTrendingFetcher,
    HackerNewsFetcher,
    TLDRFetcher,
)
import asyncio
import aiohttp


async def test_towards_data_science():
    print("=" * 70)
    print("Testing TowardsDataScienceFetcher")
    print("=" * 70)

    fetcher = TowardsDataScienceFetcher()
    async with aiohttp.ClientSession() as session:
        articles = await fetcher.fetch(session, days=1)

    if articles:
        for i, article in enumerate(articles, 1):
            print(f"\n[Article {i}]")
            print(f"  Title:     {article['title']}")
            print(f"  Author:    {article.get('author','')}")
            print(f"  Published: {article.get('published','')}")
            print(f"  URL:       {article.get('url','')}")
            print(f"  Summary:   {article.get('summary','')[:100]}...")
    else:
        print("No articles fetched.")


async def test_arxiv():
    print("\n" + "=" * 70)
    print("Testing ArxivFetcher")
    print("=" * 70)

    fetcher = ArxivFetcher()
    async with aiohttp.ClientSession() as session:
        papers = await fetcher.fetch(session)

    if papers:
        for i, paper in enumerate(papers, 1):
            print(f"\n[Paper {i}]")
            print(f"  Title:     {paper['title']}")
            print(f"  Category:  {paper.get('category','')}")
            print(f"  Authors:   {paper.get('authors','')[:100]}...")
            print(f"  Published: {paper.get('published','')}")
            print(f"  URL:       {paper.get('url','')}")
            print(f"  Summary:   {paper.get('summary','')[:100]}...")
    else:
        print("No papers fetched.")


async def test_hackernews():
    print("\n" + "=" * 70)
    print("Testing HackerNewsFetcher")
    print("=" * 70)

    fetcher = HackerNewsFetcher()
    async with aiohttp.ClientSession() as session:
        articles = await fetcher.fetch(session)

    if articles:
        for i, article in enumerate(articles, 1):
            print(f"\n[Article {i}]")
            print(f"  Title:     {article.get('title','')}")
            print(f"  Published: {article.get('published','')}")
            print(f"  URL:       {article.get('url','')}")
            print(f"  Summary:   {article.get('summary','')[:100]}...")
    else:
        print("No articles fetched.")


async def test_github_trending():
    print("\n" + "=" * 70)
    print("Testing GitHubTrendingFetcher")
    print("=" * 70)

    fetcher = GitHubTrendingFetcher()
    async with aiohttp.ClientSession() as session:
        repos = await fetcher.fetch(session, language="python", since="daily")

    if repos:
        for i, repo in enumerate(repos, 1):
            print(f"\n[Repo {i}]")
            print(f"  Title:     {repo['title']}")
            print(f"  Stars:     {repo.get('stars','')}")
            print(f"  URL:       {repo.get('url','')}")
            print(f"  Summary:   {repo.get('summary','')}...")
    else:
        print("No repos fetched.")


async def test_tldr():
    print("\n" + "=" * 70)
    print("Testing TLDRFetcher")
    print("=" * 70)

    fetcher = TLDRFetcher()
    async with aiohttp.ClientSession() as session:
        articles = await fetcher.fetch(session, days=2)

    if articles:
        for i, article in enumerate(articles, 1):
            print(f"\n[Article {i}]")
            print(f"  Title:     {article['title']}")
            print(f"  Published: {article.get('published','')}")
            print(f"  URL:       {article.get('url','')}")
            print(f"  Summary:   {article.get('summary','')[:100]}...")
    else:
        print("No articles fetched.")


if __name__ == "__main__":
    import sys

    async def main():
        if len(sys.argv) > 1:
            fetcher_name = sys.argv[1].lower()
            if fetcher_name == "tds":
                await test_towards_data_science()
            elif fetcher_name == "arxiv":
                await test_arxiv()
            elif fetcher_name == "hn":
                await test_hackernews()
            elif fetcher_name == "github":
                await test_github_trending()
            elif fetcher_name == "tldr":
                await test_tldr()
            elif fetcher_name == "all":
                await test_towards_data_science()
                await test_arxiv()
                await test_hackernews()
                await test_github_trending()
                await test_tldr()
            else:
                print(f"Unknown fetcher: {fetcher_name}")
                print("Available: tds, arxiv, hn, github, tldr, all")
        else:
            print("Usage: python test_fetcher.py [tds|arxiv|hn|github|tldr|all]")

    asyncio.run(main())
