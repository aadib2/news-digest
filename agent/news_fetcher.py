"""
news_fetcher.py
Fetches articles from the following sources:
  1. Towards Data Science (RSS)
  2. ArXiv - cs.LG, cs.AI, cs.CL (RSS)
  3. HackerNews (RSS)
  4. GitHub Trending (scrape)
  5. TLDR AI (RSS)
"""

import os
import feedparser
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone
from typing import List, Dict
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode
import asyncio
import aiohttp

# Helper functions
async def fetch_rss_feed(url: str, session: aiohttp.ClientSession):
    async with session.get(url, timeout=10) as r:
        r.raise_for_status()
        text = await r.text()

    # feedparser.parse is synchronous; run in thread to avoid blocking
    return await asyncio.to_thread(feedparser.parse, text)


# ─────────────────────────────────────────────
# 1. Towards Data Science
# ─────────────────────────────────────────────
class TowardsDataScienceFetcher:
    RSS_URL = "https://towardsdatascience.com/feed"

    async def fetch(self, session: aiohttp.ClientSession, days: int = 1) -> List[Dict]:
        feed = await fetch_rss_feed(self.RSS_URL, session)

        cutoff = datetime.now(timezone.utc) - timedelta(days=days) # one day cutoff
        articles = []

        for entry in feed.entries:
            try:
                published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            except Exception:
                published = datetime.now(timezone.utc)

            if published < cutoff:
                continue

            # Strip HTML from summary (run BeautifulSoup in thread)
            raw_summary = entry.get("summary", "")
            soup = await asyncio.to_thread(BeautifulSoup, raw_summary, "html.parser")
            clean_summary = soup.get_text()[:300]

            articles.append({
                "title": entry.title,
                "url": entry.link,
                "summary": clean_summary,
                "author": entry.get("author", "Unknown"),
                "source": "Towards Data Science",
                "published": entry.get("published", ""),
            })

        print(f"[TDS] Fetched {len(articles)} articles")
        return articles


# ─────────────────────────────────────────────
# 2. ArXiv
# ─────────────────────────────────────────────
class ArxivFetcher:
    CATEGORIES = {
        "cs.LG": "https://arxiv.org/rss/cs.LG",   # Machine Learning
        "cs.AI": "https://arxiv.org/rss/cs.AI",   # Artificial Intelligence
        "cs.CL": "https://arxiv.org/rss/cs.CL",   # Computation & Language (NLP/LLMs)
    }
    MAX_PER_CATEGORY = 15

    # Note: The RSS feeds don't return anything on Saturday and Sunday

    async def fetch(self, session: aiohttp.ClientSession) -> List[Dict]:
        papers = []
        seen_ids = set()

        for category, url in self.CATEGORIES.items():
            try:
                feed = await fetch_rss_feed(url, session)
                for entry in feed.entries[: self.MAX_PER_CATEGORY]:
                    paper_id = entry.link.split("/abs/")[-1]
                    if paper_id in seen_ids:
                        continue
                    seen_ids.add(paper_id)

                    # Clean up abstract (BeautifulSoup in thread)
                    abstract_html = entry.get("summary", "")
                    abstract_bs = await asyncio.to_thread(BeautifulSoup, abstract_html, "html.parser")
                    abstract = abstract_bs.get_text()[:400]

                    papers.append({
                        "title": entry.title.replace("\n", " ").strip(),
                        "url": entry.link,
                        "summary": abstract,
                        "authors": entry.get("author", ""),
                        "source": "ArXiv",
                        "category": category,
                        "published": entry.get("published", ""),
                    })
            except Exception as e:
                print(f"[ArXiv] Error fetching {category}: {e}")

        print(f"[ArXiv] Fetched {len(papers)} papers")
        return papers


# ─────────────────────────────────────────────
# 3. HackerNews
# ─────────────────────────────────────────────
class HackerNewsFetcher:
    RSS_URL = "https://news.ycombinator.com/rss"
    MAX_RETURNED = 20   # Pass at most this many to curator

    # URLs we don't want to surface
    SKIP_DOMAINS = {
        "news.ycombinator.com",
        "twitter.com",
        "x.com",
    }

    async def fetch(self, session: aiohttp.ClientSession) -> List[Dict]:
        try:
            feed = await fetch_rss_feed(self.RSS_URL, session)
        except Exception as e:
            print(f"[HN] Error fetching RSS feed: {e}")
            return []

        articles = []
        for entry in feed.entries[:self.MAX_RETURNED]:
            try:
                url = entry.get("link", "")
                if not url:
                    continue  # Skip entries without URLs

                # Skip unwanted domains
                domain = url.split("/")[2] if "//" in url else ""
                if any(skip in domain for skip in self.SKIP_DOMAINS):
                    continue

                articles.append({
                    "title": entry.get("title", ""),
                    "url": url,
                    "summary": "", # no summaries for this
                    "source": "HackerNews",
                    "published": entry.get("published", ""),
                })

            except Exception as e:
                print(f"[HN] Error parsing entry: {e}")
                continue

        print(f"[HN] Fetched {len(articles)} articles")
        return articles


# ─────────────────────────────────────────────
# 4. GitHub Trending
# ─────────────────────────────────────────────
class GitHubTrendingFetcher:
    BASE_URL = "https://github.com/trending"
    HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; TechDigestBot/1.0)"}

    async def fetch(self, session: aiohttp.ClientSession, language: str = "python", since: str = "daily") -> List[Dict]:
        url = f"{self.BASE_URL}/{language}?since={since}"
        try:
            async with session.get(url, headers=self.HEADERS, timeout=10) as resp:
                resp.raise_for_status()
                html = await resp.text()
        except Exception as e:
            print(f"[GitHub] Error fetching trending: {e}")
            return []

        # Parse HTML in thread
        soup = await asyncio.to_thread(BeautifulSoup, html, "html.parser")
        repos = []

        for article in soup.find_all("article", class_="Box-row"):
            try:
                # Repo name
                h2 = article.find("h2")
                if not h2:
                    continue
                link_tag = h2.find("a")
                if not link_tag:
                    continue
                repo_path = link_tag["href"].strip("/")
                repo_url = f"https://github.com/{repo_path}"

                # Description
                p = article.find("p")
                description = p.get_text(strip=True) if p else "No description"

                # Stars
                star_tag = article.find("a", {"href": f"/{repo_path}/stargazers"})
                stars = star_tag.get_text(strip=True).replace(",", "") if star_tag else "0"

                repos.append({
                    "title": f"[GitHub Trending] {repo_path}",
                    "url": repo_url,
                    "summary": description,
                    "source": "GitHub Trending",
                    "stars": stars,
                    "published": "",
                })
            except Exception as e:
                print(f"[GitHub] Error parsing repo: {e}")
                continue

        print(f"[GitHub] Fetched {len(repos)} repos")
        return repos


# ─────────────────────────────────────────────
# 5. TLDR AI
# ─────────────────────────────────────────────
class TLDRFetcher:
    RSS_URL = "https://bullrich.dev/tldr-rss/ai.rss"

    async def fetch(self, session: aiohttp.ClientSession, days: int = 2) -> List[Dict]:
        """
        Fetch TLDR AI articles from the last N days.
        Filters out sponsor entries automatically.
        Uses date-based filtering (not time-based) for daily digests.
        Defaults to 2 days to catch articles from TLDR's rolling 10-day digest.
        """
        try:
            feed = await fetch_rss_feed(self.RSS_URL, session)
        except Exception as e:
            print(f"[TLDR AI] Error fetching RSS feed: {e}")
            return []

        # For daily digest, use date comparison (ignore time component)
        cutoff_date = (datetime.now(timezone.utc) - timedelta(days=days)).date()
        print(cutoff_date)
        articles = []

        for entry in feed.entries:
            try:
                # Parse publication date
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                else:
                    published = datetime.now(timezone.utc)

                # Filter by date cutoff (compare dates, not datetimes)
                if published.date() < cutoff_date:
                    continue

                # Skip sponsor entries
                title = entry.get("title", "")
                if "sponsor" in title.lower():
                    continue

                # Strip HTML from summary (run BeautifulSoup in thread)
                raw_summary = entry.get("summary", "")
                soup = await asyncio.to_thread(BeautifulSoup, raw_summary, "html.parser")
                clean_summary = soup.get_text()[:300]

                articles.append({
                    "title": title,
                    "url": entry.get("link", ""),
                    "summary": clean_summary,
                    "source": "TLDR AI",
                    "published": entry.get("published", ""),
                })

            except Exception as e:
                print(f"[TLDR AI] Error parsing entry: {e}")
                continue

        print(f"[TLDR AI] Fetched {len(articles)} articles from last {days} day(s)")
        return articles
    


# ─────────────────────────────────────────────
# Master Fetcher
# ─────────────────────────────────────────────
class NewsFetcher:
    def __init__(self):
        self.fetchers = {
            "towards_data_science": TowardsDataScienceFetcher(),
            "arxiv": ArxivFetcher(),
            "hackernews": HackerNewsFetcher(),
            "github_trending": GitHubTrendingFetcher(),
            "tldr_ai": TLDRFetcher(),
        }

    async def fetch_all(self, session: aiohttp.ClientSession = None) -> List[Dict]:
        """Fetch from all sources (runs asynchronously). Returns combined list.
        If `session` is provided it will be reused; otherwise a temporary session is created.
        """
        all_articles = []

        created_session = False
        if session is None:
            connector = aiohttp.TCPConnector(limit=10)
            session = aiohttp.ClientSession(connector=connector)
            created_session = True

        try:
            tasks = [fetcher.fetch(session) for fetcher in self.fetchers.values()]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for name, res in zip(self.fetchers.keys(), results):
                if isinstance(res, Exception):
                    print(f"[NewsFetcher] Source '{name}' failed: {res}")
                    continue
                if isinstance(res, list):
                    all_articles.extend(res)
        finally:
            if created_session:
                await session.close()

        print(f"[NewsFetcher] Total raw articles (before dedupe): {len(all_articles)}")

        # --- Deduplicate articles by normalized URL ---
        def normalize_url(url: str) -> str:
            try:
                p = urlparse(url or "")
                # Remove common tracking query params (utm_*, gclid, fbclid)
                qs = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True) if not (k.startswith("utm_") or k in ("gclid", "fbclid"))]
                new_query = urlencode(qs)
                cleaned = urlunparse((p.scheme, p.netloc.lower(), p.path.rstrip('/'), '', new_query, ''))
                return cleaned
            except Exception:
                return url or ""

        # Load previously sent article URLs for deduplication (uses SQLite DB)
        feedback_urls = set()
        try:
            from feedback_store import get_sent_urls
            sent_urls = get_sent_urls()
            feedback_urls = {normalize_url(u) for u in sent_urls}
            print(f"[NewsFetcher] Loaded {len(feedback_urls)} previously-sent URLs from feedback DB")
        except Exception as e:
            print(f"[NewsFetcher] Warning: couldn't load sent URLs from feedback DB: {e}")

        seen = set()
        deduped = []
        for art in all_articles:
            url = art.get("url", "")
            n = normalize_url(url)
            if not n:
                # fallback to title-based dedupe
                title_key = art.get("title", "").strip().lower()
                if title_key in seen:
                    continue
                seen.add(title_key)
                deduped.append(art)
                continue

            # Skip if already sent in feedback
            if n in feedback_urls:
                continue

            if n in seen:
                continue
            seen.add(n)
            deduped.append(art)

        print(f"[NewsFetcher] Total articles after dedupe & feedback filtering: {len(deduped)}")
        return deduped
