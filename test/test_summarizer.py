"""
test_summarizer.py
Unit tests for parse_summary() — splitting Claude's digest summary into
its Technical Summary and Why It Matters parts.
Run: uv run python -m test.test_summarizer
"""

from agent.summarizer_agent import parse_summary


def test_typical_output():
    text = (
        "Technical Summary\n\n"
        "Transformers process tokens in parallel using self-attention. "
        "This paper introduces a linear-time variant.\n\n"
        "**Why it matters:** Faster attention cuts inference cost for on-device ML."
    )
    tech, why = parse_summary(text)
    assert "Transformers" in tech
    assert "Technical Summary" not in tech
    assert why == "Faster attention cuts inference cost for on-device ML."
    print("✅ test_typical_output passed")


def test_case_insensitive_marker():
    text = "Something useful.\n\n**Why It Matters:** Big deal for RAG pipelines."
    tech, why = parse_summary(text)
    assert tech == "Something useful."
    assert why == "Big deal for RAG pipelines."
    print("✅ test_case_insensitive_marker passed")


def test_unbolded_marker():
    text = "Something useful.\n\nWhy it matters: Big deal."
    tech, why = parse_summary(text)
    assert tech == "Something useful."
    assert why == "Big deal."
    print("✅ test_unbolded_marker passed")


def test_no_marker_falls_back():
    text = "Only a technical summary with no takeaway sentence."
    tech, why = parse_summary(text)
    assert tech == text
    assert why == ""
    print("✅ test_no_marker_falls_back passed")


def test_empty_and_fallback_text():
    assert parse_summary("") == ("", "")
    assert parse_summary("No preview available - check link for more info.") == (
        "No preview available - check link for more info.", ""
    )
    print("✅ test_empty_and_fallback_text passed")


if __name__ == "__main__":
    test_typical_output()
    test_case_insensitive_marker()
    test_unbolded_marker()
    test_no_marker_falls_back()
    test_empty_and_fallback_text()
    print("\n🎉 All summarizer parse tests passed!")
