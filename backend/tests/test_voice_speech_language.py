"""Offline pronunciation-language decisions for real-time voice TTS."""
import pytest
from app.voice.speech_language import select_reply_tts_language


@pytest.mark.parametrize("answer,fallback,want", [
    ("はい、こんにちは。今日はどんなことを知りたいですか？", "en", "ja"),
    ("私の名前はAqlyraです。日本語で質問してください。", "en", "ja"),
    ("আমি Aqlyra। আপনার প্রশ্নের উত্তর দিতে পারি।", "en", "bn"),
    ("হ্যাঁ, আমি বাংলায় উত্তর দিচ্ছি।", "ja", "bn"),
    ("मैं आपकी कैसे मदद कर सकता हूँ?", "en", "hi"),
    ("This explanation is in English, with the term বাংলা as an example.", "en", "en"),
    ("The phrase こんにちは means hello in English and is a simple Japanese greeting.", "en", "en"),
    ("Sure, I can help with documents, calculations and engineering.", "bn", "en"),
    ("", "ja", "ja"),
    ("Yes.", "bn", "bn"),
    ("Yes, I can explain this in English.", "ja", "en"),
    ("Ami Bangla te kotha bolte pari, tomake help korbo.", "bn", "bn"),
    ("Tomar kemon ache bolo, ami answer korbo.", "bn", "bn"),
    ("Yes, I can explain this in English.", "bn", "en"),
])
def test_reply_language_prevents_mismatched_voice_accents(answer, fallback, want):
    assert select_reply_tts_language(answer=answer, fallback=fallback) == want


def test_language_selection_is_bounded_and_does_not_require_network():
    assert select_reply_tts_language(
        answer="English explanation " * 10000,
        fallback="en",
    ) == "en"


def test_real_agent_uses_reply_language_for_tts_not_just_user_transcript():
    from pathlib import Path
    source = (Path(__file__).parents[1] / "app" / "voice" / "worker.py").read_text()
    assert "select_reply_tts_language(" in source
    assert "answer=generated.result.content," in source
    assert "self._tts_model.update_options(" in source
    assert "session.interrupt(force=True)" in source
