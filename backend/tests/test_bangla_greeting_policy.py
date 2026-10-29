"""Regression: Bangla welcome style must be user-respectful across Converse paths.

The greeting is a product-level default, NOT a prediction of user religion.
The user's explicitly preferred greeting always overrides that default.
"""
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

import app.services.chat_service as chat_module
from app.api.dependencies import get_current_user
from app.llms import LLMGeneration, LLMProviderInfo
from app.models.user import User
from app.main import app


class CaptureBanglaProvider:
    def __init__(self):
        self.calls = []

    @property
    def info(self):
        return LLMProviderInfo(
            provider_name="bangla-policy-test",
            model_name="mock-instructions",
            max_output_tokens=512,
        )

    def generate(self, *, instructions, input_text):
        self.calls.append((instructions, input_text))
        return LLMGeneration(
            text="আসসালামু আলাইকুম! অবশ্যই, বাংলায় কথা বলব।",
            provider_name="bangla-policy-test",
            model_name="mock-instructions",
            response_id="bangla-test-1",
            input_tokens=4,
            output_tokens=12,
            total_tokens=16,
        )


def test_bangla_converse_language_switch_respects_preferred_welcome(
    client: TestClient, db_session: Session, monkeypatch
):
    user = User(
        email="bangla-welcome@example.com",
        username="bangla_welcome",
        hashed_password="test-only",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    app.dependency_overrides[get_current_user] = lambda: user
    provider = CaptureBanglaProvider()
    monkeypatch.setattr(
        chat_module, "create_configured_llm_provider", lambda: provider
    )
    conversation = client.post(
        "/api/v1/conversations",
        json={"title": "Bangla greeting preference", "mode": "normal"},
    )
    assert conversation.status_code == 201
    response = client.post(
        f"/api/v1/conversations/{conversation.json()['id']}/messages",
        json={"content": "Talk me bangla"},
    )
    assert response.status_code == 200
    assert response.json()["assistant_message"]["content"].startswith(
        "আসসালামু আলাইকুম"
    )
    assert len(provider.calls) == 1
    instructions, input_text = provider.calls[0]
    assert "Talk me bangla" in input_text
    assert "আসসালামু আলাইকুম" in instructions
    assert "নমস্কার" in instructions
    assert "explicit user preference" in instructions
    assert "every turn" in instructions


def test_uploaded_converse_uses_the_same_bangla_greeting_policy():
    instructions = chat_module._NORMAL_ATTACHMENT_INSTRUCTIONS
    assert "আসসালামু আলাইকুম" in instructions
    assert "নমস্কার" in instructions
    assert "religion or identity" in instructions


def test_normal_converse_does_not_assume_user_religion():
    instructions = chat_module._NORMAL_CHAT_INSTRUCTIONS
    assert "religion or identity" in instructions
    assert '"হ্যালো"' in instructions
    assert "no greeting" in instructions
