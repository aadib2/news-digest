"""
news_fetcher.py
Fetches articles from all 5 Phase 1A sources:
  1. Towards Data Science (RSS)
  2. ArXiv - cs.LG, cs.AI, cs.CL (RSS)
  3. HackerNews (RSS)
  4. GitHub Trending (scrape)
  5. Dev.to (API)
"""

import requests
import feedparser
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone
from typing import List, Dict
import time


# ─────────────────────────────────────────────
# 1. Towards Data Science
# ─────────────────────────────────────────────
class TowardsDataScienceFetcher:
    RSS_URL = "https://towardsdatascience.com/feed"

    def fetch(self, days: int = 1) -> List[Dict]:
        feed = feedparser.parse(self.RSS_URL)
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        articles = []

        for entry in feed.entries:
            try:
                published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            except Exception:
                published = datetime.now(timezone.utc)

            if published < cutoff:
                continue

            # Strip HTML from summary
            raw_summary = entry.get("summary", "")
            soup = BeautifulSoup(raw_summary, "html.parser")
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

    def fetch(self) -> List[Dict]:
        papers = []
        seen_ids = set()

        for category, url in self.CATEGORIES.items():
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries[: self.MAX_PER_CATEGORY]:
                    paper_id = entry.id.split("/abs/")[-1]
                    if paper_id in seen_ids:
                        continue
                    seen_ids.add(paper_id)

                    # Clean up abstract
                    abstract = BeautifulSoup(
                        entry.get("summary", ""), "html.parser"
                    ).get_text()[:400]

                    papers.append({
                        "title": entry.title.replace("\n", " ").strip(),
                        "url": f"https://arxiv.org/abs/{paper_id}",
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

    def fetch(self) -> List[Dict]:
        try:
            feed = feedparser.parse(self.RSS_URL)
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
                    "summary": entry.get("summary", "")[:300],
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

    def fetch(self, language: str = "python", since: str = "daily") -> List[Dict]:
        url = f"{self.BASE_URL}/{language}?since={since}"
        try:
            response = requests.get(url, headers=self.HEADERS, timeout=10)
            response.raise_for_status()
        except Exception as e:
            print(f"[GitHub] Error fetching trending: {e}")
            return []

        soup = BeautifulSoup(response.content, "html.parser")
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
# 5. Dev.to
# ─────────────────────────────────────────────
class DevToFetcher:
    BASE_URL = "https://dev.to/api/articles"
    TAGS = ["machinelearning", "datascience", "dataengineering", "deeplearning", "ai"]
    PER_TAG = 8

    def fetch(self) -> List[Dict]:
        articles = []
        seen_urls = set()

        for tag in self.TAGS:
            try:
                params = {"tag": tag, "per_page": self.PER_TAG, "top": "week"}
                response = requests.get(self.BASE_URL, params=params, timeout=10)
                response.raise_for_status()

                for item in response.json():
                    url = item.get("url", "")
                    if url in seen_urls:
                        continue
                    seen_urls.add(url)

                    articles.append({
                        "title": item.get("title", ""),
                        "url": url,
                        "summary": item.get("description", "")[:300],
                        "author": item.get("user", {}).get("name", "Unknown"),
                        "source": "Dev.to",
                        "tags": item.get("tag_list", []),
                        "published": item.get("published_at", ""),
                    })

            except Exception as e:
                print(f"[Dev.to] Error fetching tag '{tag}': {e}")
                continue

        print(f"[Dev.to] Fetched {len(articles)} articles")
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
            "devto": DevToFetcher(),
        }

    def fetch_all(self) -> List[Dict]:
        """Fetch from all sources. Returns combined list."""
        all_articles = []
        for name, fetcher in self.fetchers.items():
            try:
                articles = fetcher.fetch()
                all_articles.extend(articles)
            except Exception as e:
                print(f"[NewsFetcher] Source '{name}' failed: {e}")

        print(f"[NewsFetcher] Total raw articles: {len(all_articles)}")
        return all_articles
