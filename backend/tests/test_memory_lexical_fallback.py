"""Lexical memory recall remains private and grounded without embeddings."""
from app.config.settings import settings
from app.models.memory import Memory
from app.models.user import User
from app.services.memory_lexical_retrieval import retrieve_lexical_memories_for_user
import app.services.chat_service as chat_service


def _user(db, label):
    user = User(username=label, email=f"{label}@example.org", hashed_password="test-hash")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _memory(db, user, text, active=True):
    mem = Memory(
        user_id=str(user.id), kind="fact",
        content=text, normalized_content=text.casefold(),
        importance=0.8, confidence=0.9, is_active=active,
    )
    db.add(mem)
    db.commit()
    return mem


def test_lexical_memory_owner_and_active_boundary(db_session):
    alice = _user(db_session, "memory_lexical_alice")
    bob = _user(db_session, "memory_lexical_bob")
    m = _memory(db_session, alice, "My apartment rent is 56000 yen monthly")
    _memory(db_session, bob, "My apartment rent is 99000 yen monthly")
    _memory(db_session, alice, "My apartment rent used to be 1234 yen", active=False)
    hits = retrieve_lexical_memories_for_user(
        db=db_session, user_id=str(alice.id),
        query_text="What is my apartment rent?", top_k=5,
    )
    assert len(hits) == 1
    assert hits[0].memory_id == m.id
    assert "56000" in hits[0].content
    assert hits[0].cosine_distance is None
    assert hits[0].retrieval_mode == "lexical"


def test_memory_recall_ignores_unrelated_and_secret_like_facts(db_session):
    user = _user(db_session, "memory_lexical_no_leak")
    _memory(db_session, user, "My password for the apartment is abc")
    _memory(db_session, user, "I prefer Python programming")
    assert not retrieve_lexical_memories_for_user(
        db=db_session, user_id=str(user.id), query_text="apartment"
    )
    assert not retrieve_lexical_memories_for_user(
        db=db_session, user_id=str(user.id), query_text="My grocery list"
    )
    assert len(retrieve_lexical_memories_for_user(
        db=db_session, user_id=str(user.id), query_text="Python programming"
    )) == 1


def test_converse_uses_fallback_when_vector_provider_fails(db_session, monkeypatch):
    user = _user(db_session, "memory_lexical_fallback")
    _memory(db_session, user, "My apartment rent is 56000 yen")
    monkeypatch.setattr(settings, "MEMORY_CHAT_ENABLED", True)
    monkeypatch.setattr(settings, "MEMORY_CHAT_LEXICAL_FALLBACK_ENABLED", True)
    monkeypatch.setattr(settings, "EMBEDDING_PROVIDER", "huggingface")
    monkeypatch.setattr(
        chat_service, "retrieve_memories_for_user",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("quota exhausted")),
    )
    hits = chat_service._retrieve_normal_chat_memories(
        db=db_session, user_id=str(user.id), message="My rent?"
    )
    assert len(hits) == 1
    assert hits[0].retrieval_mode == "lexical"
    assert "56000" in hits[0].content


def test_lexical_mode_without_semantic_provider(db_session, monkeypatch):
    user = _user(db_session, "memory_lexical_direct")
    _memory(db_session, user, "I prefer Japanese technical explanations")
    monkeypatch.setattr(settings, "MEMORY_CHAT_ENABLED", True)
    monkeypatch.setattr(settings, "MEMORY_CHAT_LEXICAL_FALLBACK_ENABLED", True)
    monkeypatch.setattr(settings, "EMBEDDING_PROVIDER", "deterministic")
    monkeypatch.setattr(
        chat_service, "retrieve_memories_for_user",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("no fake vectors")),
    )
    hits = chat_service._retrieve_normal_chat_memories(
        db=db_session, user_id=str(user.id), message="Japanese explanations"
    )
    assert len(hits) == 1
    assert hits[0].retrieval_mode == "lexical"
