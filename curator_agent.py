"""
curator_agent.py
Uses Claude to rank articles by relevance to the user's interest profile.
Returns the top N articles with relevance scores and reasons.
"""

import json
import re
from typing import List, Dict
from anthropic import Anthropic


class CuratorAgent:
    def __init__(self, interests: Dict):
        self.client = Anthropic()
        self.interests = interests
        self.max_articles = interests.get("max_articles_per_digest", 8)
        self.min_score = interests.get("min_relevance_score", 55)

    def rank_articles(
        self, articles: List[Dict], feedback_summary: Dict = None
    ) -> List[Dict]:
        """
        Send articles to Claude for relevance ranking.
        Returns top N articles sorted by relevance score.
        """
        if not articles:
            return []

        # Trim article list to avoid huge prompts — send top 60 max
        articles_to_rank = articles[:60]

        # Build a lean representation (title + summary + source only)
        slim_articles = [
            {
                "id": i,
                "title": a["title"],
                "summary": a.get("summary", "")[:200],
                "source": a["source"],
            }
            for i, a in enumerate(articles_to_rank)
        ]

        # Build feedback context if available
        feedback_ctx = ""
        if feedback_summary:
            feedback_ctx = f"""
Recent feedback from the user:
- Upvoted articles: {feedback_summary.get('upvoted_count', 0)}
- Downvoted articles: {feedback_summary.get('downvoted_count', 0)}
- Most engaged topics: {', '.join(feedback_summary.get('top_topics', []))}
Use this to nudge relevance scores accordingly.
"""

        prompt = f"""You are a technical news curator for a software engineer and data scientist.

USER INTERESTS:
- Primary: machine_learning (35%), data_science (25%), data_engineering (20%), general_tech (20%)
- High interest keywords: {', '.join(self.interests['high_interest_keywords'][:20])}
- Low interest keywords: {', '.join(self.interests['low_interest_keywords'])}
{feedback_ctx}

TASK:
Rank each article by relevance to this user. Be selective and critical.

For each article return:
- id (same as input)
- relevance_score: integer 0-100
- category: one of [machine_learning, data_science, data_engineering, general_tech, skip]
- reason: one short sentence explaining the score

Use category "skip" for anything clearly irrelevant.
Only score >= {self.min_score} articles will be shown to the user.

ARTICLES:
{json.dumps(slim_articles, indent=2)}

Return ONLY a valid JSON array. No markdown, no explanation, no preamble.
Example format:
[{{"id": 0, "relevance_score": 82, "category": "machine_learning", "reason": "Introduces a novel finetuning approach for LLMs."}}]"""

        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = response.content[0].text.strip()

            # Strip markdown fences if present
            raw = re.sub(r"^```[a-z]*\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw)

            rankings = json.loads(raw)

        except json.JSONDecodeError as e:
            print(f"[Curator] JSON parse error: {e}")
            return articles[: self.max_articles]
        except Exception as e:
            print(f"[Curator] Claude API error: {e}")
            return articles[: self.max_articles]

        # Map scores back to original articles
        score_map = {
            r["id"]: r
            for r in rankings
            if r.get("category") != "skip" and r.get("relevance_score", 0) >= self.min_score
        }

        ranked = []
        for idx, article in enumerate(articles_to_rank):
            if idx in score_map:
                enriched = article.copy()
                enriched["relevance_score"] = score_map[idx]["relevance_score"]
                enriched["category"] = score_map[idx]["category"]
                enriched["reason"] = score_map[idx]["reason"]
                ranked.append(enriched)

        # Sort by relevance score descending
        ranked.sort(key=lambda x: x["relevance_score"], reverse=True)

        top = ranked[: self.max_articles]
        print(f"[Curator] Ranked {len(ranked)} relevant articles → returning top {len(top)}")
        return top
