"""Select spoken language from the AI reply rather than only the user prompt.

This is a deterministic, network-free supplement to STT language metadata.
A response can switch language even when the question was in English:
"Answer in Japanese" -> 「もちろん。...」.
"""
from __future__ import annotations


def select_reply_tts_language(*, answer: str, fallback: str = "en") -> str:
    """Avoid English-accent TTS for substantial Bengali/Japanese/Hindi replies.

    Ignore a short isolated foreign phrase in an otherwise English answer.
    Japanese Han glyphs count only alongside Kana to avoid confusing
    Chinese, and short excerpts never force an unintended language change.
    """
    content = answer[:12000]
    bengali = sum("\u0980" <= c <= "\u09ff" for c in content)
    devanagari = sum("\u0900" <= c <= "\u097f" for c in content)
    kana = sum(
        ("\u3040" <= c <= "\u30ff") or ("\u31f0" <= c <= "\u31ff")
        for c in content
    )
    han = sum("\u3400" <= c <= "\u9fff" for c in content) if kana else 0
    japanese = kana + han
    latin = sum(
        ("a" <= c.lower() <= "z")
        for c in content
        if c.isascii()
    )
    candidates = {"bn": bengali, "ja": japanese, "hi": devanagari}
    language, count = max(candidates.items(), key=lambda item: item[1])
    # Require a substantial non-Latin passage, not a quoted glossary word.
    if count >= 5 and count >= latin * 0.28:
        return language
    # A user may be speaking Bengali but explicitly request an English
    # answer. Read a genuinely English reply in English rather than
    # inheriting the user's Bengali TTS accent.
    if latin >= 12 and latin >= max(count, 1) * 3:
        return "en"
    return fallback
