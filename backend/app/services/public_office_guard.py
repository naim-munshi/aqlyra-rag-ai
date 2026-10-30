"""Conservative protection for time-sensitive public officeholder questions.

No hardcoded politicians, country guesses, private memory, or web calls.
This module prevents unverified LLM answers when live sourcing is unavailable.
"""
from __future__ import annotations

import re
from collections.abc import Iterator
from datetime import datetime, timezone

from app.llms.types import LLMGeneration, LLMProviderInfo, LLMStreamEvent


_ROLE = re.compile(
    r"\b(?:prime\s+minister|president|head\s+of\s+(?:state|government))\b"
    r"|প্রধানমন্ত্রী|রাষ্ট্রপতি|首相|総理大臣|大統領",
    flags=re.IGNORECASE,
)
_ASKING_WHO = re.compile(
    r"\bwho(?:'s| is|\s+currently\s+is)?\b|\bwho\b"
    r"|কে(?:\s|\?|$)|কার\b|誰|だれ",
    flags=re.IGNORECASE,
)
_GENERIC_EN = re.compile(
    r"(?:who(?:'s| is)|tell me who(?:'s| is))\s+"
    r"(?:(?:the|our)\s+)?(?:(?:current|present)\s+)?"
    r"(?:prime\s+minister|president|head\s+of\s+(?:state|government))"
    r"(?:\s+(?:now|today|right now|currently))?",
    flags=re.IGNORECASE,
)
_GENERIC_BN = re.compile(
    r"(?:(?:বর্তমান|এখনকার)\s+)?(?:প্রধানমন্ত্রী|রাষ্ট্রপতি)\s*"
    r"(?:কে|কে আছেন)",
)
_GENERIC_JA = re.compile(
    r"(?:(?:今の|現在の)\s*)?(?:首相|総理大臣|大統領)"
    r"(?:は)?(?:誰|だれ)(?:ですか)?",
)
_TERMINAL_PUNCTUATION = re.compile(r"[\s!?।。？]+$")
_HISTORICAL = re.compile(
    r"\b(?:was|were|former|previous|historical|history|in\s+(?:19|20)\d{2})\b"
    r"|সাবেক|প্রাক্তন|以前|過去|歴代",
    flags=re.IGNORECASE,
)


def _normalized(question: str) -> str:
    return " ".join(question.replace("’", "'").split()).strip()


def is_public_officeholder_question(question: str) -> bool:
    """Only questions asking *who* holds a public executive office."""
    text = _normalized(question)
    if not _ROLE.search(text) or not _ASKING_WHO.search(text):
        return False
    # Don't add a hard live-data requirement to a request explicitly about
    # past incumbents; the ordinary historical-answer path remains available.
    if _HISTORICAL.search(text):
        return False
    return True


def is_ambiguous_public_officeholder_question(question: str) -> bool:
    """Exact generic queries lack the country/jurisdiction needed to answer."""
    text = _normalized(question)
    text = _TERMINAL_PUNCTUATION.sub("", text)
    return any(pattern.fullmatch(text) for pattern in (
        _GENERIC_EN, _GENERIC_BN, _GENERIC_JA,
    ))


def _language(question: str) -> str:
    if any("\u0980" <= ch <= "\u09ff" for ch in question):
        return "bn"
    if any("\u3040" <= ch <= "\u30ff" or "\u3400" <= ch <= "\u9fff" for ch in question):
        return "ja"
    return "en"


def unverified_officeholder_reply(question: str) -> str | None:
    """Return a bounded response if an LLM would otherwise guess a live fact.

    Called only on the ordinary (non-web) chat path. A real verified web
    request does not call this function and preserves its sources.
    """
    if not is_public_officeholder_question(question):
        return None
    lang = _language(question)
    ambiguous = is_ambiguous_public_officeholder_question(question)
    if lang == "bn":
        return (
            "কোন দেশের প্রধানমন্ত্রী বা রাষ্ট্রপতির কথা বলছেন?"
            if ambiguous else
            "এই পদে বর্তমানে কে আছেন, তা লাইভ সূত্র দিয়ে যাচাই করতে পারছি না। "
            "Web Search চালু করে আবার জিজ্ঞেস করুন।"
        )
    if lang == "ja":
        return (
            "どの国の首相・大統領についてですか？"
            if ambiguous else
            "現在の在職者をライブ情報で確認できません。"
            "ウェブ検索を有効にして再度お試しください。"
        )
    return (
        "Which country do you mean?"
        if ambiguous else
        "I can't verify the current officeholder from live sources right now. "
        "Please enable Web Search or try again when it is available."
    )


def officeholder_search_query(question: str) -> str:
    """Add an as-of date to public search without transmitting chat history."""
    if not is_public_officeholder_question(question):
        return question
    date = datetime.now(timezone.utc).date().isoformat()
    return f"{question.strip()} current officeholder as of {date} official government source"


class PublicFactGuardProvider:
    """Fixed, truthful user-visible reply with the normal streaming contract."""
    def __init__(self, response: str):
        self._response = response

    @property
    def info(self) -> LLMProviderInfo:
        return LLMProviderInfo(
            provider_name="aqlyra-public-fact-guard",
            model_name="local-validation",
            max_output_tokens=256,
        )

    def generate(self, *, instructions: str, input_text: str) -> LLMGeneration:
        return LLMGeneration(
            text=self._response,
            provider_name=self.info.provider_name,
            model_name=self.info.model_name,
        )

    def stream(self, *, instructions: str, input_text: str) -> Iterator[LLMStreamEvent]:
        result = self.generate(instructions=instructions, input_text=input_text)
        yield LLMStreamEvent(event_type="delta", delta_text=self._response)
        yield LLMStreamEvent(event_type="complete", generation=result)
