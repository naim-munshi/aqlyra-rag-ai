"""Mixed-script RAG evidence must not vanish behind incidental English FTS.

Uses synthetic isolated PostgreSQL uploads, no paid LLM, external requests or
production data. The feature is off by default pending real load measurement.
"""
from dataclasses import replace

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config.settings import settings
from app.retrieval import RetrievalQuery
from app.services import lexical_retrieval_service as lexical


def _owner(client: TestClient, tag: str):
    email = f"multilingual-fusion-{tag}@example.org"
    register = client.post(
        "/api/v1/auth/register",
        json={
            "username": f"fusion_{tag}",
            "email": email,
            "password": "SyntheticPass123!",
        },
    )
    assert register.status_code == 201, register.text
    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "SyntheticPass123!"},
    )
    assert login.status_code == 200, login.text
    header = {"Authorization": f"Bearer {login.json()['access_token']}"}
    profile = client.get("/api/v1/users/me", headers=header)
    assert profile.status_code == 200
    return profile.json()["id"], header


def _upload(client: TestClient, header, filename: str, content: str):
    uploaded = client.post(
        "/api/v1/documents/upload",
        headers=header,
        files={"file": (filename, ("# Source\n\n" + content).encode(), "text/markdown")},
    )
    assert uploaded.status_code == 201, uploaded.text
    document_id = uploaded.json()["id"]
    process = client.post(
        f"/api/v1/documents/{document_id}/process",
        headers=header,
    )
    assert process.status_code == 200, process.text
    return document_id


def test_mixed_japanese_and_english_fuses_true_matches_and_isolates_users(
    client: TestClient, db_session: Session, monkeypatch,
):
    alice, ah = _owner(client, "jp_a")
    bob, bh = _owner(client, "jp_b")
    distractor = _upload(
        client, ah, "english.md",
        "Our support team handles general questions about scheduling.",
    )
    target = _upload(
        client, ah, "japanese.md",
        "東京工芸大学の研究室では画像認識の実験を毎週水曜日に行います。",
    )
    private = _upload(
        client, bh, "private.md",
        "東京工芸大学の研究室では機密データを保存しています。",
    )
    monkeypatch.setattr(
        settings, "KNOWLEDGE_MULTILINGUAL_UNICODE_FUSION_ENABLED", True,
    )
    query = RetrievalQuery(
        user_id=alice,
        text="support 東京工芸大学の研究室",
        document_ids=(target, distractor, private),
        chunk_roles=("content",),
        top_k=5,
    )
    hits = lexical.search_lexical_chunks(db_session, query)
    assert hits
    assert hits[0].document_id == target
    assert any(hit.document_id == distractor for hit in hits)
    assert all(hit.document_id != private for hit in hits)
    assert len({h.chunk_id for h in hits}) == len(hits)
    assert hits[0].metadata["lexical_channels"]
    assert hits[0].metadata["multilingual_rrf_score"] > 0

    # The same private text cannot appear in a different user's results.
    blocked = lexical.search_lexical_chunks(
        db_session, replace(query, user_id=bob, document_ids=(target,)),
    )
    assert blocked == []
    narrowed = lexical.search_lexical_chunks(
        db_session, replace(query, document_ids=(distractor,)),
    )
    assert all(hit.document_id == distractor for hit in narrowed)


def test_mixed_bangla_and_english_retrieves_bangla_evidence(
    client: TestClient, db_session: Session, monkeypatch,
):
    owner, header = _owner(client, "bn_a")
    generic = _upload(
        client, header, "english-refund.md",
        "Refund requests must include an order identifier.",
    )
    actual = _upload(
        client, header, "bangla-refund.md",
        "ফেরতের সময়সীমা পাঁচ কর্মদিবস এবং গ্রাহককে ইমেইল পাঠানো হয়।",
    )
    monkeypatch.setattr(
        settings, "KNOWLEDGE_MULTILINGUAL_UNICODE_FUSION_ENABLED", True,
    )
    hits = lexical.search_lexical_chunks(
        db_session,
        RetrievalQuery(
            user_id=owner,
            text="refund ফেরতের সময়সীমা",
            top_k=5,
            document_ids=(generic, actual),
            chunk_roles=("content",),
        ),
    )
    assert hits
    assert hits[0].document_id == actual
    assert all(h.document_id in {generic, actual} for h in hits)


def test_default_disabled_and_english_only_do_not_issue_extra_unicode_sql(
    client: TestClient, db_session: Session, monkeypatch,
):
    owner, header = _owner(client, "english")
    doc_id = _upload(client, header, "simple.md", "Support hours are 9 to 5.")
    def unexpected(*args, **kwargs):
        raise AssertionError("Unexpected Unicode SQL path")
    monkeypatch.setattr(lexical, "_fallback_unicode_chunks", unexpected)
    query = RetrievalQuery(
        user_id=owner, document_ids=(doc_id,), top_k=3,
        text="support hours", chunk_roles=("content",),
    )
    monkeypatch.setattr(
        settings, "KNOWLEDGE_MULTILINGUAL_UNICODE_FUSION_ENABLED", True,
    )
    assert lexical.search_lexical_chunks(db_session, query)
    monkeypatch.setattr(
        settings, "KNOWLEDGE_MULTILINGUAL_UNICODE_FUSION_ENABLED", False,
    )
    assert lexical.search_lexical_chunks(db_session, query)


def test_rrf_is_deterministic_bounded_and_does_not_fabricate_dense_scores():
    def item(chunk_id: str, score: float, mode: str):
        return lexical.LexicalRetrievalHit(
            chunk_id=chunk_id, document_id="owner-doc",
            original_filename="synthetic.md",
            parent_chunk_id=None, chunk_role="content",
            chunk_level=0, chunk_index=0,
            source_label="p1", section_path=(),
            content="synthetic", start_page=None, end_page=None,
            lexical_score=score, metadata={"lexical_match": mode},
        )
    fts = [item("english", 0.95, "fts"), item("both", 0.75, "fts")]
    unicode = [item("both", 3.0, "unicode"), item("japanese", 2.0, "unicode")]
    fused = lexical._fuse_multilingual_lexical_hits(
        fts_hits=fts, unicode_hits=unicode, top_k=2,
    )
    assert [h.chunk_id for h in fused] == ["both", "japanese"]
    assert fused[0].lexical_score == 0.75  # actual FTS metric, not RRF
    assert fused[0].metadata["lexical_channels"] == ["fts", "unicode_substring"]
    assert fused[1].lexical_score == 2.0  # actual Unicode n-gram matches
    assert all("semantic_similarity" not in h.metadata for h in fused)
    again = lexical._fuse_multilingual_lexical_hits(
        fts_hits=fts, unicode_hits=unicode, top_k=2,
    )
    assert [h.chunk_id for h in again] == [h.chunk_id for h in fused]
