"""
test_curator.py
Test the curator agent without needing Discord.
Run with: python test_curator.py
"""

import json
from agent.curator_agent import CuratorAgent

# Load interests
with open("interests.json") as f:
    interests = json.load(f)

# Sample articles for testing
SAMPLE_ARTICLES = [
    {
        "title": "Larger Context Windows Don't Fix RAG — So I Built a System That Does",
        "url": "https://towardsdatascience.com/rag-example",
        "summary": "This article explores RAG systems and how to improve them without just increasing context window size.",
        "source": "Towards Data Science",
        "author": "Test Author",
    },
    {
        "title": "Parse PDFs for RAG Locally with Docling",
        "url": "https://towardsdatascience.com/pdf-parsing",
        "summary": "A guide to parsing PDFs locally for RAG applications using the Docling library.",
        "source": "Towards Data Science",
        "author": "Test Author",
    },
    {
        "title": "OpenAI Acquired Ona for Long-Running Agents",
        "url": "https://openai.com/news/ona",
        "summary": "OpenAI announced acquisition of Ona to bring secure cloud execution for agents.",
        "source": "TLDR AI",
    },
    {
        "title": "DiffusionGemma: 4x faster text generation",
        "url": "https://blog.google/gemma",
        "summary": "Google released DiffusionGemma, a new approach to faster text generation using diffusion models.",
        "source": "TLDR AI",
    },
    {
        "title": "Music Assistant is a free media library manager",
        "url": "https://github.com/music-assistant/server",
        "summary": "An open source music library management system.",
        "source": "GitHub Trending",
        "stars": "2005",
    },
    {
        "title": "Noise infusion banned from statistical products by Census Bureau",
        "url": "https://desfontain.es/blog/banning-noise.html",
        "summary": "Statistical privacy discussion about noise injection in census data.",
        "source": "HackerNews",
    },
]


async def test_curator_ranking():
    """Test the curator agent's ranking functionality."""
    print("=" * 70)
    print("Testing CuratorAgent.rank_articles()")
    print("=" * 70)
    print(f"\nInput: {len(SAMPLE_ARTICLES)} sample articles\n")

    curator = CuratorAgent(interests)

    try:
        ranked = await curator.rank_articles(SAMPLE_ARTICLES)

        print(f"\n✅ Successfully ranked {len(ranked)} articles\n")

        if ranked:
            for i, article in enumerate(ranked, 1):
                print(f"[{i}] {article['title'][:60]}")
                print(f"    Score: {article.get('relevance_score', 'N/A')}/100")
                print(f"    Category: {article.get('category', 'N/A')}")
                print(f"    Reason: {article.get('reason', 'N/A')}")
                print(f"    Source: {article['source']}")
                print(f"    Reading Time: {article['reading_time']}")
                print()
        else:
            print("⚠️  No articles passed the relevance threshold.")

        return True

    except json.JSONDecodeError as e:
        print(f"\n❌ JSON parse error: {e}")
        print("This means the JSON extraction strategies failed.")
        return False
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False


def test_json_extraction():
    """Test the JSON extraction with various malformed inputs."""
    print("\n" + "=" * 70)
    print("Testing _extract_json_from_text() with malformed inputs")
    print("=" * 70)

    curator = CuratorAgent(interests)

    test_cases = [
        # Valid case
        (
            'Test case 1: Plain JSON',
            '[{"id": 0, "relevance_score": 85, "category": "machine_learning / AI", "reason": "Test"}]',
        ),
        # Markdown fences
        (
            "Test case 2: JSON with markdown fences",
            '```json\n[{"id": 0, "relevance_score": 85, "category": "machine_learning / AI", "reason": "Test"}]\n```',
        ),
        # Extra text before/after
        (
            "Test case 3: JSON with preamble and markdown",
            'Here is the ranking:\n```json\n[{"id": 0, "relevance_score": 85, "category": "machine_learning / AI", "reason": "Test"}]\n```\nEnd of response.',
        ),
        # Line-by-line extraction
        (
            "Test case 4: JSON spread across lines with prose",
            'Based on the articles provided, here is my ranking:\n[\n  {"id": 0, "relevance_score": 85, "category": "machine_learning / AI", "reason": "Test"}\n]\nThis completes the ranking.',
        ),
        # extra test
        (
            "test case 5: JSON with new lines",
            '```json\n [\n {"id": 0, "relevance_score": 72, "category": "machine_learning / AI", "reason": "Practical guidance on Claude model usage and preventing hallucinations in LLM applications."},\n {"id": 1, "relevance_score": 85, "category": "machine_learning / AI", "reason": "Directly addresses vision LLMs and RAG applications with PDF parsing for enterprise document intelligence."}```'
        )
    ]

    passed = 0
    for name, test_input in test_cases:
        try:
            result = curator._extract_json_from_text(test_input)
            if isinstance(result, list) and len(result) > 0:
                print(f"✅ {name}: PASS")
                print(result)
                print(len(result))
                passed += 1
            else:
                print(f"❌ {name}: FAIL (result is not a non-empty list)")
        except Exception as e:
            print(f"❌ {name}: FAIL ({str(e)[:50]})")

    print(f"\nPassed: {passed}/{len(test_cases)}")
    return passed == len(test_cases)


if __name__ == "__main__":
    import asyncio

    print("\n🧪 Curator Agent Test Suite\n")

    # Test JSON extraction first (doesn't need API)
    extraction_ok = test_json_extraction()

    # Test actual ranking (needs API)
    print("\n" + "=" * 70)
    print("Running ranking test (requires ANTHROPIC_API_KEY)")
    print("=" * 70)
    ranking_ok = asyncio.run(test_curator_ranking())

    # Summary
    print("\n" + "=" * 70)
    print("Test Summary")
    print("=" * 70)
    print(f"JSON Extraction: {'✅ PASS' if extraction_ok else '❌ FAIL'}")
    print(f"Ranking with Claude: {'✅ PASS' if ranking_ok else '❌ FAIL'}")
    print()
