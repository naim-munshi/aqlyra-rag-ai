"""Bounded, opt-in/automatic web routing for NORMAL conversations only.

Never send conversation history, private RAG files, memory or attachment text
to the public web provider. This module only classifies the current question.
"""
import re
from typing import Literal

from app.config.settings import settings

WebMode = Literal["auto", "off", "on", "deep"]

_EXPLICIT_SEARCH = re.compile(
    r"\b(search (?:the )?web|web search|search online|look (?:it )?up online|"
    r"google (?:it|this)|browse (?:the )?web|find (?:it )?online|deep research)\b"
    r"|ওয়েবে খুঁজ|ওয়েবে খুঁজ|ইন্টারনেটে খুঁজ|ওয়েব সার্চ|ওয়েব সার্চ|"
    r"ウェブ検索|ネットで調べ|インターネットで調べ",
    re.IGNORECASE,
)
_NO_WEB = re.compile(
    r"\b(?:don't|do not|without|no) (?:use |do )?(?:web|internet|browsing|search)\b"
    r"|ওয়েব (?:ব্যবহার|সার্চ) করো না|ওয়েব (?:ব্যবহার|সার্চ) করো না"
    r"|検索しないで|ウェブを使わないで",
    re.IGNORECASE,
)
_CURRENT = re.compile(
    r"\b(?:latest|current|recent|recently|today|tonight|tomorrow|yesterday|"
    r"right now|this week|this month|this year|breaking|newest|"
    r"live scores?|as of (?:today|now)|updated|2026|2027|2028)\b"
    r"|最新|現在|今日|今週|今年|速報|"
    r"সর্বশেষ|আজকের|আজকে|এখনকার|বর্তমান|নতুন খবর|এই সপ্তাহ|"
    r"এই মাস",
    re.IGNORECASE,
)
_QUESTION = re.compile(
    r"\?|\b(?:what|which|who|when|where|how|is|are|can|find|show|"
    r"compare|check|verify|tell me|give me|list)\b"
    r"|কি|কী|কবে|কোথায়|কোথায়|কেমন|খুঁজ|দেখাও|বলো|"
    r"とは|ですか|調べ|教えて|比較",
    re.IGNORECASE,
)
_PRIVATE_ONLY = re.compile(
    r"\b(?:my uploaded|my private document|my file|our internal file|"
    r"my password|my api key|my otp|my conversation|our chat history)\b"
    r"|আমার আপলোড|আমার ব্যক্তিগত ফাইল|私のアップロード",
    re.IGNORECASE,
)
_DEEP = re.compile(r"\b(?:deep research|in.depth research|comprehensive research)\b|গভীর গবেষণা|詳細調査", re.IGNORECASE)
_COMPARE = re.compile(r"\b(?:compare|comparison|versus|vs\.?|trade.offs?)\b|তুলনা|比較", re.IGNORECASE)
_FACT_CHECK = re.compile(r"\b(?:fact.check|verify (?:the )?claim|is it true)\b|সত্যতা যাচাই|ファクトチェック", re.IGNORECASE)


def choose_web_mode(question: str, mode: WebMode = "auto") -> str | None:
    """Return supported research mode or None. Defaults to no external disclosure."""
    if mode == "off" or _NO_WEB.search(question):
        return None
    if mode not in ("auto", "on", "deep"):
        raise ValueError("Unsupported web mode")
    if mode == "auto":
        if not settings.WEB_RESEARCH_ENABLED:
            return None
        if _PRIVATE_ONLY.search(question) and not _EXPLICIT_SEARCH.search(question):
            return None
        if not _EXPLICIT_SEARCH.search(question) and not (
            _CURRENT.search(question) and _QUESTION.search(question)
        ):
            return None
    if mode == "deep" or _DEEP.search(question):
        return "deep"
    if _FACT_CHECK.search(question):
        return "fact_check"
    if _COMPARE.search(question):
        return "compare"
    return "search"


def cited_web_answer(answer: str, sources: list) -> str:
    """Append clickable, checked-source links without trusting source titles as Markdown."""
    entries = []
    for source in sources:
        title = re.sub(r"[\[\]()\r\n<>]", " ", source.title).strip()[:160]
        url = source.url.replace(")", "%29")
        entries.append(f"- {source.citation} [{title or 'Source'}]({url})")
    return answer.rstrip() + "\n\n**Web sources**\n" + "\n".join(entries)
