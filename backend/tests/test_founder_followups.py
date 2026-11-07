"""Founder identity follow-ups are contextual, factual and privacy preserving."""
from app.api.dependencies import get_current_user
from app.main import app
from app.models.user import User
from app.product_identity.service import resolve_founder_followup_answer


FOUNDER = "Aqlyra-এর প্রতিষ্ঠাতা ও নির্মাতা Md Naim।"


def test_bengali_founder_work_and_home_followup():
    result = resolve_founder_followup_answer(
        "সে কি কাজ করে কোথায় থাকে?",
        last_assistant_content=FOUNDER,
    )
    assert result is not None
    assert "AI ও RAG" in result
    assert "ঠিকানা অনুমান করে বলব না" in result
    assert "টোকিও" not in result


def test_unrelated_pronoun_never_assumes_founder():
    assert resolve_founder_followup_answer(
        "সে কি কাজ করে কোথায় থাকে?",
        last_assistant_content="This conversation is about an unrelated person.",
    ) is None
    assert resolve_founder_followup_answer(
        "সে কি কাজ করে কোথায় থাকে?",
        last_assistant_content=None,
    ) is None


def test_unrelated_followup_does_not_trigger_hard_coded_profile():
    assert resolve_founder_followup_answer(
        "এখন কোডিং শুরু করো",
        last_assistant_content=FOUNDER,
    ) is None


def test_explicit_founder_name_without_previous_context():
    reply = resolve_founder_followup_answer(
        "What work does Aqlyra founder Md Naim do and where does he live?",
        last_assistant_content=None,
    )
    assert reply is not None
    assert "AI and RAG software" in reply
    assert "verified public residential" in reply


def test_founder_followup_in_real_converse_api(client, db_session):
    user = User(
        email="identity-followup@example.com",
        username="identityfollowup",
        hashed_password="test-only",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    app.dependency_overrides[get_current_user] = lambda: user

    created = client.post(
        "/api/v1/conversations",
        json={"title": "Founder facts", "mode": "normal"},
    )
    assert created.status_code == 201
    conversation_id = created.json()["id"]
    first = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"content": "Aqlyra-এর প্রতিষ্ঠাতা কে?"},
    )
    assert first.status_code == 200
    assert first.json()["assistant_message"]["content"] == FOUNDER

    followup = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"content": "সে কি কাজ করে কোথায় থাকে?"},
    )
    assert followup.status_code == 200
    data = followup.json()["assistant_message"]
    assert data["provider_name"] == "aqlyra-system"
    assert "AI ও RAG" in data["content"]
    assert "ঠিকানা অনুমান করে বলব না" in data["content"]
    assert data["citations"] == []
