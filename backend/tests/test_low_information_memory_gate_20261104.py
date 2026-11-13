"""Prevent redundant paid-provider calls for exact greetings only.

No network, real users, provider keys or production writes. Memory safety and
all meaningful user statements continue using the existing extraction path.
"""
from unittest.mock import Mock

import pytest
from sqlalchemy.orm import Session

from app.config.settings import settings
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.user import User
from app.services import chat_service
from app.services.memory_extraction_service import extract_memories_for_message
from app.services.social_turn_policy import is_low_information_social_turn


@pytest.mark.parametrize("social", [
    "hi", "Hi!", "hello", "Hey there?", "thanks", "Thank you.",
    "assalamu alaikum", "SALAM", "dhonnobad", "হ্যালো",
    "আসসালামু আলাইকুম", "ধন্যবাদ", "こんにちは", "おはようございます",
    "ありがとうございます", "bye",
])
def test_pure_social_turn_is_bounded_and_multilingual(social):
    assert is_low_information_social_turn(social)


@pytest.mark.parametrize("meaningful", [
    "Hi, remember that I prefer Bangla.",
    "hello can you explain quantum computing?",
    "Hi what did we talk about last time?",
    "Thanks, please forget my address.",
    "I live in Tokyo",
    "Who is Bangladesh's prime minister?",
    "হাই আমি নতুন চাকরি পেয়েছি",
    "こんにちは、前に話した内容を覚えていますか",
    "hello " + "x" * 100,
])
def test_any_meaningful_content_still_uses_normal_memory(meaningful):
    assert not is_low_information_social_turn(meaningful)


def test_greeting_does_not_call_semantic_or_lexical_provider(monkeypatch):
    monkeypatch.setattr(settings, "MEMORY_CHAT_ENABLED", True)
    monkeypatch.setattr(settings, "MEMORY_CHAT_LEXICAL_FALLBACK_ENABLED", True)
    monkeypatch.setattr(
        chat_service,
        "retrieve_memories_for_user",
        lambda **kwargs: pytest.fail("Trivial greeting should not embed"),
    )
    monkeypatch.setattr(
        chat_service,
        "_retrieve_lexical_chat_memories",
        lambda **kwargs: pytest.fail("Trivial greeting should not need lexical"),
    )
    assert chat_service._retrieve_normal_chat_memories(
        db=Mock(), user_id="synthetic", message="হ্যালো!",
    ) == ()


def test_non_social_question_still_retrieves_authorized_memory(monkeypatch):
    monkeypatch.setattr(settings, "MEMORY_CHAT_ENABLED", True)
    monkeypatch.setattr(settings, "MEMORY_CHAT_LEXICAL_FALLBACK_ENABLED", False)
    monkeypatch.setattr(settings, "EMBEDDING_PROVIDER", "remote_onnx")
    calls = []
    monkeypatch.setattr(
        chat_service,
        "retrieve_memories_for_user",
        lambda **kwargs: calls.append(kwargs) or [],
    )
    chat_service._retrieve_normal_chat_memories(
        db=Mock(), user_id="owner", message="Hi, what language do I prefer?",
    )
    assert len(calls) == 1
    assert calls[0]["user_id"] == "owner"


def test_owned_greeting_is_not_sent_to_memory_extraction_llm(db_session: Session):
    user = User(
        email="social-gate-owner@example.com",
        username="social-gate-owner",
        hashed_password="fake-hash",
    )
    db_session.add(user)
    db_session.flush()
    conversation = Conversation(
        user_id=str(user.id), title="Greeting only", mode="normal",
    )
    db_session.add(conversation)
    db_session.flush()
    message = Message(
        conversation_id=conversation.id,
        role="user", mode="normal", content="こんにちは",
        citations=[], is_refusal=False,
    )
    db_session.add(message)
    db_session.commit()

    provider = Mock()
    provider.generate.side_effect = AssertionError(
        "Do not run Groq for trivial memory extraction"
    )

    memories = extract_memories_for_message(
        db=db_session, user_id=str(user.id),
        source_message_id=str(message.id), provider=provider,
    )
    assert memories == []
    provider.generate.assert_not_called()


def test_unauthorized_greeting_still_checks_message_owner(db_session: Session):
    from uuid import uuid4
    from app.services.memory_extraction_service import (
        MemoryExtractionValidationError,
    )
    owner = User(
        email="social-gate-foreign@example.com",
        username="social-gate-foreign",
        hashed_password="fake-hash",
    )
    db_session.add(owner)
    db_session.flush()
    conversation = Conversation(
        user_id=str(owner.id), title="Private greeting", mode="normal",
    )
    db_session.add(conversation)
    db_session.flush()
    message = Message(
        conversation_id=conversation.id,
        role="user", mode="normal", content="Hello",
        citations=[], is_refusal=False,
    )
    db_session.add(message)
    db_session.commit()
    with pytest.raises(MemoryExtractionValidationError):
        extract_memories_for_message(
            db=db_session, user_id=str(uuid4()),
            source_message_id=str(message.id), provider=Mock(),
        )
