"""
curator_agent.py
Uses Claude to rank articles by relevance to the user's interest profile (interests.json).
Returns the top N articles with relevance scores and reasons.
"""

import asyncio
import json
import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict
import re

# Prefer AsyncAnthropic if available; otherwise fall back to sync Anthropic and run in thread
try:
    from anthropic import AsyncAnthropic as AnthropicClient
    _ANTHROPIC_ASYNC = True
except Exception:
    try:
        from anthropic import Anthropic as AnthropicClient
        _ANTHROPIC_ASYNC = False
    except Exception:
        AnthropicClient = None
        _ANTHROPIC_ASYNC = False


class CuratorAgent:
    def __init__(self, interests: Dict):
        if AnthropicClient is None:
            raise RuntimeError("Anthropic client library not available")
        # instantiate client (async or sync implementation)
        try:
            self.client = AnthropicClient(timeout=30.0)
        except TypeError:
            # some clients expect api_key or no args
            self.client = AnthropicClient()
        self.interests = interests
        self.max_articles = interests.get("max_articles_per_digest", 8)
        self.min_score = interests.get("min_relevance_score", 55)
        self.prefilter_limit = interests.get("prefilter_limit", 25) # set pre-filter limit to 25
        self._log_dir = Path("logs/curator")
        self._log_dir.mkdir(parents=True, exist_ok=True)

    def _prefilter_articles(self, articles: List[Dict], limit: int = None) -> List[Dict]:
        """
        Score articles by keyword relevance, return top `limit`.
        Uses high/medium/low interest keywords from config.
        """
        if limit is None:
            limit = self.prefilter_limit

        if len(articles) <= limit:
            return articles

        high_kw = [k.lower() for k in self.interests.get('high_interest_keywords', [])]
        med_kw = [k.lower() for k in self.interests.get('medium_interest_keywords', [])]
        low_kw = [k.lower() for k in self.interests.get('low_interest_keywords', [])]

        def make_pattern(keywords):
            # word-boundary match per keyword, case-insensitive, compiled once
            escaped = [re.escape(k) for k in keywords]
            return re.compile(r'\b(' + '|'.join(escaped) + r')\b', re.IGNORECASE) if escaped else None # ensures we just match whole words

        high_pat = make_pattern(high_kw)
        med_pat = make_pattern(med_kw)
        low_pat = make_pattern(low_kw)

        def score(article):
            title = article.get('title', '')
            summary = article.get('summary', '')

            s = 0
            if high_pat:
                s += 3 * len(high_pat.findall(title))
                s += 1 * len(high_pat.findall(summary))
            if med_pat:
                s += 1.5 * len(med_pat.findall(title))
                s += 0.5 * len(med_pat.findall(summary))
            if low_pat:
                s -= 2 * len(low_pat.findall(title))
                s -= 1 * len(low_pat.findall(summary))

            return s

        scored = sorted(articles, key=score, reverse=True)
        return scored[:limit]

    def _log_raw_response(self, raw: str, suffix: str = "") -> None:
        """Log raw Claude response to file for debugging."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = self._log_dir / f"claude_response_{timestamp}{suffix}.txt"
        try:
            filename.write_text(raw, encoding="utf-8")
        except Exception:
            pass  # Fail silently to not disrupt main flow

    def _extract_json_from_text(self, text: str) -> List[Dict]:
        """
        Strictly extract JSON array from Claude's response.
        Handles markdown fences and attempts to parse truncated responses.
        """
        if not text:
            raise json.JSONDecodeError("Empty response", "", 0)

        raw = text.strip()

        # Remove markdown fences if present
        raw = re.sub(r'^```[a-zA-Z]*\n?', '', raw)
        raw = re.sub(r'\n?```$', '', raw)
        raw = raw.strip()

        # Strategy 1: Direct parsing
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError:
            pass

        # Strategy 2: Bracket extraction
        start_idx = raw.find("[")
        end_idx = raw.rfind("]")

        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            extracted = raw[start_idx : end_idx + 1]
            try:
                parsed = json.loads(extracted)
                if isinstance(parsed, list):
                    return parsed
            except json.JSONDecodeError:
                pass

        # Strategy 3: Handle potential truncation by attempting common closures
        if start_idx != -1:
            truncated = raw[start_idx:]
            # Try appending closures to fix truncated JSON
            for closure in ["]", "}]", '"}]', '"} \n]']:
                try:
                    parsed = json.loads(truncated + closure)
                    if isinstance(parsed, list):
                        return parsed
                except json.JSONDecodeError:
                    continue

        raise json.JSONDecodeError(
            f"Could not extract valid JSON array. Raw start: {raw[:200]!r}", raw, 0
        )

    async def rank_articles(
        self, articles: List[Dict], feedback_summary: Dict = None
    ) -> List[Dict]:
        """
        Send articles to Claude for relevance ranking.
        Pre-filters articles by keyword relevance, then has Claude rank and return top N.
        Returns top N articles sorted by relevance score.
        Raises exception if JSON parsing fails (no fallback).
        """
        if not articles:
            return []

        # Pre-filter articles by keyword relevance to reduce token usage
        articles_prefiltered = self._prefilter_articles(articles, self.prefilter_limit)
        articles_to_rank = articles_prefiltered[:self.prefilter_limit] # extra check

        # Build a lean representation (title + summary + source + url)
        slim_articles = [
            {
                "title": a["title"],
                "summary": a.get("summary", "")[:200],
                "source": a["source"],
                "url": a.get("url", ""),
            }
            for a in articles_to_rank
        ]

        # Build feedback context if available
        feedback_ctx = ""
        if feedback_summary:
            feedback_ctx = f"""
Recent feedback from the user:
- Upvoted articles: {feedback_summary.get('upvoted_count', 0)}
- Downvoted articles: {feedback_summary.get('downvoted_count', 0)}
- Most engaged topics: {', '.join(feedback_summary.get('top_topics', []))}
Use this to nudge relevance scores accordingly. If values are empty or 0, then ignore.
"""
        # crafting prompt including interests, slim article representation, and user feedback (upvotes, downvotes)
        # System-level instruction enforces strict JSON-only output from Claude.
        system_prompt = (
            "You are a technical news curator for an aspiring AI/ML engineer and data scientist and current CS student."
            "Your ONLY output must be a single raw JSON array. Do NOT output any prose, markdown, code fences, or explanations. "
            "If you cannot produce the normal array, return a single-element array with {\"error\": "
            "\"<brief reason>\", \"raw\": \"<original raw response>\"}. "
            f"Return ONLY the top {self.max_articles} most relevant articles, ranked by relevance_score descending. "
            "Each array element must be an object with fields: title (string), url (string), source (string), "
            "category (one of: \"machine_learning / AI\", \"data_science\", \"software_engineering\", \"general_tech\"), "
            "relevance_score (integer 0-100), reason (one short sentence). "
            "Use double quotes for strings and valid JSON."
        )

        prompt = f"""
USER INTERESTS:
- Primary: machine_learning / AI (30%), data_science (25%), software_engineering (25%), general_tech (20%)
- High interest keywords: {', '.join(self.interests['high_interest_keywords'])}
- Medium interest keywords: {', '.join(self.interests['medium_interest_keywords'])}
- Low interest keywords: {', '.join(self.interests['low_interest_keywords'])}
{feedback_ctx}

TASK:
Select and rank the top {self.max_articles} most relevant articles for this user. Be selective and critical.

For each article return:
- title: exact title from input
- url: exact URL from input
- source: exact source from input
- category: one of [machine_learning / AI, data_science, software_engineering, general_tech]
- relevance_score: integer 0-100
- reason: one short sentence explaining the score

Only include articles with relevance_score >= {self.min_score}.
If fewer than {self.max_articles} articles meet the threshold, return only those that do.

ARTICLES:
{json.dumps(slim_articles, indent=2)}

Return ONLY a valid JSON array. No markdown, no explanation, no preamble.
Example format:
[{{\"title\": \"Article Title\", \"url\": \"https://example.com\", \"source\": \"Example\", \"category\": \"machine_learning / AI\", \"relevance_score\": 82, \"reason\": \"Introduces a novel finetuning approach for LLMs.\"}}]"""

        try:
            if _ANTHROPIC_ASYNC:
                response = await self.client.messages.create(
                    model="claude-haiku-4-5-20251001",
                    max_tokens=2000,
                    cache_control={"type": "ephemeral"},
                    system=system_prompt,
                    messages=[{"role": "user", "content": prompt}],
                )
            else:
                # run sync client in thread
                response = await asyncio.to_thread(
                    self.client.messages.create,
                    {
                        "model": "claude-haiku-4-5",
                        "max_tokens": 2000,
                        "cache_control": {"type": "ephemeral"},
                        "system": system_prompt,
                        "messages": [{"role": "user", "content": prompt}],
                    },
                )
            raw = response.content[0].text.strip()

            # Log raw response for debugging
            self._log_raw_response(raw)

            print(f"[Curator] Raw Claude response (first 500 chars):\n{raw[:500]}\n")

            # Use robust JSON extraction
            rankings = self._extract_json_from_text(raw)

            if not isinstance(rankings, list):
                raise ValueError(f"Expected JSON array, got {type(rankings)}")

            print(f"[Curator] Successfully parsed {len(rankings)} rankings from Claude")

        except json.JSONDecodeError as e:
            print(f"[Curator] JSON parse error: {e}")
            print(f"[Curator] Raw response: {raw[:500]}")
            self._log_raw_response(raw, "_parse_error") # log raw output from error
            raise
        except Exception as e:
            print(f"[Curator] Error: {e}")
            self._log_raw_response(raw, "_error")
            raise

        # Enrich returned articles with full original data (match by title + url)
        article_map = {
            (a["title"], a.get("url", "")): a
            for a in articles_to_rank
        }

        enriched = []
        for ranked in rankings:
            key = (ranked["title"], ranked.get("url", ""))
            if key in article_map:
                full = article_map[key].copy()
                full["relevance_score"] = ranked["relevance_score"]
                full["category"] = ranked["category"]
                full["reason"] = ranked["reason"]
                enriched.append(full)

        print(f"[Curator] Ranked {len(enriched)} relevant articles → returning top {len(enriched)}")
        return enriched
