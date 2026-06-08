"""
summarizer_agent.py
Uses Claude to generate a tight, technical 2-3 sentence summary
and a "why it matters" takeaway for each curated article.
"""

from anthropic import Anthropic


class SummarizerAgent:
    def __init__(self):
        self.client = Anthropic()

    def summarize(self, article: dict) -> str:
        """
        Returns a formatted string:
          Summary: ...
          Why it matters: ...
        """
        prompt = f"""You are summarizing a tech article for a current CS student and aspiring data professional and ML engineer.

        Article:
        Title: {article['title']}
        Source: {article['source']}
        Content preview: {article.get('summary', 'No preview available.')[:400]}

        Write:
        1. A 2-3 sentence technical summary (what is it, what does it do/show?)
        2. One sentence: "**Why it matters:**" followed by the key takeaway for an ML/data engineer

        Rules:
        - Be concise and specific, not vague
        - Use technical language freely
        - Do NOT restate the title
        - Do NOT include the URL
        - Do NOT use bullet points, just two short paragraphs"""

        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=250,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text.strip()
        except Exception as e:
            print(f"[Summarizer] Error: {e}")
            # Graceful fallback
            return article.get("summary", "No summary available.")[:300]
