"""
summarizer_agent.py
Uses Claude to generate a tight, technical 2-3 sentence summary
and a "why it matters" takeaway for each curated article.
"""

import asyncio

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


class SummarizerAgent:
    def __init__(self):
        if AnthropicClient is None:
            raise RuntimeError("Anthropic client library not available")
        try:
            self.client = AnthropicClient(timeout=30.0)
        except TypeError:
            self.client = AnthropicClient()

    async def summarize(self, article: dict) -> str:
        """
        Returns a formatted string:
          Summary: ...
          Why it matters: ...
        """
        prompt = f"""You are summarizing a tech article for a current CS student and aspiring data professional and ML/AI engineer.

        Article:
        Title: {article['title']}
        Source: {article['source']}
        Content preview: {article.get('summary', 'No preview available.')[:400]}

        Write:
        1. A 2-3 sentence technical summary (what is it, what does it do/show?) - title this "Technical Summary"
        2. One sentence: "**Why it matters:**" followed by the key takeaway for an ML/AI or data engineer.

        Rules:
        - Be concise and specific, not vague
        - If there is no preview available, fall back to stating "No preview available - check link for more info."
        - Use technical language freely
        - Do NOT restate the title
        - Do NOT include the URL
        - Do NOT use bullet points, just two short paragraphs"""

        try:
            if _ANTHROPIC_ASYNC:
                response = await self.client.messages.create(
                    model="claude-haiku-4-5-20251001",
                    max_tokens=250,
                    messages=[{"role": "user", "content": prompt}],
                )
            else:
                response = await asyncio.to_thread(
                    self.client.messages.create,
                    {
                        "model": "claude-haiku-4-5-20251001",
                        "max_tokens": 250,
                        "messages": [{"role": "user", "content": prompt}],
                    },
                )
            return response.content[0].text.strip()
        except Exception as e:
            print(f"[Summarizer] Error: {e}")
            # Graceful fallback
            return article.get("summary", "No summary available.")[:300]
