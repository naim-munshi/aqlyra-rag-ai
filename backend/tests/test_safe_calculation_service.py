"""Exact calculation is part of Aqlyra's existing normal-chat brain."""
import pytest

from app.services.safe_calculation_service import exact_calculation_reply


@pytest.mark.parametrize("question,expected", [
    ("What is two plus two?", "The answer is 4."),
    ("Calculate 17 * 19", "The answer is 323."),
    ("how much is 3 divided by 4?", "The answer is 0.75."),
    ("compute (2 + 4) * 3", "The answer is 18."),
    ("12.5 + 0.05", "The answer is 12.55."),
    ("১০ গুণ ৩ কত", "উত্তর: 30।"),
    ("12 かける 3 は", "答えは36です。"),
    ("2 to the power of 3", "The answer is 8."),
])
def test_direct_spoken_arithmetic_routes_without_llm(question, expected):
    assert exact_calculation_reply(question) == expected


@pytest.mark.parametrize("question", [
    "What is the capital of Bangladesh?",
    "Tell me about you.",
    "How much is rent in Tokyo today?",
    "Calculate the latest exchange rate for JPY/USD.",
    "What is 2 million plus 3?",
    "__import__('os').system('echo hijack')",
    "1 / 0",
    "99999999999999999999999999 * 999999999999999",
    "2 ** 999999",
    "1 + " * 1000,
])
def test_untrusted_or_narrative_questions_do_not_execute_math(question):
    assert exact_calculation_reply(question) is None


def test_calculator_is_used_by_existing_chat_and_therefore_voice():
    from pathlib import Path
    source = (Path(__file__).parents[1] / "app" / "services" / "chat_service.py").read_text()
    assert "exact_calculation_reply(cleaned)" in source
    assert "def execute_chat_turn(" in source
