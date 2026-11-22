"""Conservative zero-model gate for turns with no durable memory content.

Only self-contained social tokens qualify. Do NOT use semantic similarity,
truncate arbitrary messages, or classify messages that append a request
("Hi, remember that ...") as greetings. This gate saves a remote vector
lookup and memory-extraction LLM call without changing chat generation.
"""
from __future__ import annotations


_SMALLTALK_EXACT: frozenset[str] = frozenset({
    "hi", "hello", "hey", "hello there", "hey there",
    "good morning", "good afternoon", "good evening",
    "bye", "goodbye", "see you", "thanks", "thank you",
    "hii", "hey bro", "hi bro",
    "salam", "assalamualaikum", "assalamu alaikum",
    "dhonnobad",
    "হাই", "হ্যালো", "সালাম", "আসসালামু আলাইকুম",
    "ধন্যবাদ", "বিদায়", "বিদায়",
    "こんにちは", "こんばんは", "おはよう", "おはようございます",
    "ありがとう", "ありがとうございます", "さようなら",
})


def is_low_information_social_turn(message: str) -> bool:
    """True only for exact small talk, never a request or private statement."""
    if not isinstance(message, str) or len(message) > 72:
        return False
    normalized = " ".join(
        message.strip(" \t\r\n.,!?।？！。…،").casefold().split()
    )
    return normalized in _SMALLTALK_EXACT
