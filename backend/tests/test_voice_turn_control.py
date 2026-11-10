"""Regression tests for voice stop commands and per-turn relevance."""
from pathlib import Path

import pytest

from app.voice.turn_control import is_stop_speaking_command


@pytest.mark.parametrize("transcript", [
    "Stop!", "please stop", "STOP SPEAKING.", "that's enough",
    "থামো", "এখন থামো।", "চুপ করো", "আর বলো না",
    "thamo", "chup koro", "ar bolo na",
    "止めて", "もういい", "話すのをやめて。",
])
def test_stop_commands_interrupt_without_ai_response(transcript):
    assert is_stop_speaking_command(transcript) is True


@pytest.mark.parametrize("question", [
    "How do I stop a Docker container?",
    "Tell me why the train stopped",
    "Explain Japanese grammar",
    "When should I stop exercising?",
    "Why does my algorithm stop early?",
    "stop the engine by editing the source code",
    "থামো শব্দের মানে কী?",
    "止めてってどういう意味ですか",
])
def test_instructional_questions_are_not_muted(question):
    assert is_stop_speaking_command(question) is False


def test_worker_uses_same_chat_brain_but_does_not_pollute_user_question():
    source = (Path(__file__).parents[1] / "app" / "voice" / "worker.py").read_text()
    assert "execute_chat_turn(" in source
    assert "message=user_text," in source
    assert "[VOICE LANGUAGE RULE]" not in source
    assert "is_stop_speaking_command(user_text)" in source
    assert "session.interrupt(force=True)" in source
    assert '"min_duration": 0.3' in source
