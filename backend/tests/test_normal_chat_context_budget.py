"""Pure normal-chat payload tests; no external provider or private data."""
import json
from types import SimpleNamespace

from app.services.chat_service import (
    _NORMAL_CHAT_MAX_INPUT_BYTES,
    _normal_chat_input,
)


def _message(index: int, *, body: str):
    return SimpleNamespace(role="user" if index % 2 == 0 else "assistant", content=body)


def _memory(content: str):
    return SimpleNamespace(kind="preference", content=content)


def _payload(*, history=(), current="hello", memories=()):
    raw = _normal_chat_input(
        history=list(history), current_message=current, memories=tuple(memories),
    )
    return raw, json.loads(raw)


def test_small_payload_preserves_all_context_and_memory():
    history = [_message(0, body="Earlier question"), _message(1, body="Earlier answer")]
    raw, data = _payload(
        history=history,
        current="What about it?",
        memories=[_memory("Use Japanese")],
    )
    assert data["current_user_message"] == "What about it?"
    assert data["conversation_history"] == [
        {"role": "user", "content": "Earlier question"},
        {"role": "assistant", "content": "Earlier answer"},
    ]
    assert data["personal_memory_context"] == [
        {"kind": "preference", "content": "Use Japanese"},
    ]
    assert len(raw.encode("utf-8")) < _NORMAL_CHAT_MAX_INPUT_BYTES


def test_long_history_keeps_recent_contiguous_turns_and_current_message():
    history = [_message(i, body=f"turn-{i} " + "x" * 6500) for i in range(10)]
    raw, data = _payload(history=history, current="Please continue")
    kept = data["conversation_history"]
    assert kept
    assert len(kept) < len(history)
    assert kept[-1]["content"] == history[-1].content
    assert [item["content"] for item in kept] == [
        entry.content for entry in history[-len(kept):]
    ]
    assert data["current_user_message"] == "Please continue"
    assert len(raw.encode("utf-8")) <= _NORMAL_CHAT_MAX_INPUT_BYTES


def test_oversize_latest_turn_does_not_replace_it_with_irrelevant_older_turn():
    history = [
        _message(0, body="unrelated older topic"),
        _message(1, body="y" * (_NORMAL_CHAT_MAX_INPUT_BYTES + 1)),
    ]
    raw, data = _payload(history=history, current="new question")
    assert data["conversation_history"] == []
    assert data["current_user_message"] == "new question"
    assert len(raw.encode("utf-8")) <= _NORMAL_CHAT_MAX_INPUT_BYTES


def test_multilingual_context_is_bounded_by_utf8_bytes_not_characters():
    history = [
        _message(i, body=("日本語 বাংলা " * 1100) + f"turn-{i}")
        for i in range(5)
    ]
    raw, data = _payload(history=history, current="最新の質問")
    assert len(raw.encode("utf-8")) <= _NORMAL_CHAT_MAX_INPUT_BYTES
    assert data["current_user_message"] == "最新の質問"
    assert data["conversation_history"][-1]["content"] == history[-1].content


def test_memory_budget_leaves_room_for_chat_and_never_emits_memory_metadata():
    memories = [_memory("m" * 4500), _memory("n" * 4500), _memory("p" * 4500)]
    history = [_message(0, body="prior user"), _message(1, body="prior assistant")]
    raw, data = _payload(history=history, current="now", memories=memories)
    assert len(data["personal_memory_context"]) == 1
    assert [x["content"] for x in data["conversation_history"]] == [
        "prior user", "prior assistant",
    ]
    assert len(raw.encode("utf-8")) <= _NORMAL_CHAT_MAX_INPUT_BYTES
    assert "similarity_score" not in raw


def test_current_user_message_is_never_silently_truncated():
    current = "current " + "z" * (_NORMAL_CHAT_MAX_INPUT_BYTES + 5)
    raw, data = _payload(
        history=[_message(0, body="old")],
        current=current,
        memories=[_memory("not included")],
    )
    assert data["current_user_message"] == current
    assert data["conversation_history"] == []
    assert data["personal_memory_context"] == []
    # The HTTP/API input limit remains responsible for an oversized new turn.
    assert len(raw.encode("utf-8")) > _NORMAL_CHAT_MAX_INPUT_BYTES
