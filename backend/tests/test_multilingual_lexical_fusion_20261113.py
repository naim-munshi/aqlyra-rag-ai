"""Mixed-script RAG evidence must not vanish behind incidental English FTS.

Uses synthetic isolated PostgreSQL uploads, no paid LLM, external requests or
production data. The feature is off by default pending real load measurement.
"""
import json
import math
import time

from sqlalchemy import select

from app.models.document_chunk import DocumentChunk
from app.retrieval.evaluation import RetrievalEvaluationCase, evaluate_rankings

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


def test_unicode_query_terms_cover_later_japanese_and_bangla_phrases():
    # An early long Japanese span must not consume the entire 16-term cap.
    japanese = (
        "これは前置きとしてとても長い文章を書いていますが"
        "ここからが質問の本題になります。東京工芸大学"
    )
    jp_terms = lexical._unicode_search_terms(japanese)
    assert jp_terms
    assert len(jp_terms) <= 16
    assert any(term in "東京工芸大学" for term in jp_terms)

    bangla = (
        "বাংলাদেশেরক্রেতাদেরজন্যঅনেকদীর্ঘএকটিপ্রশ্ন।"
        "ফেরতেরসময়সীমা"
    )
    bn_terms = lexical._unicode_search_terms(bangla)
    assert bn_terms
    assert len(bn_terms) <= 16
    assert any(term in "ফেরতেরসময়সীমা" for term in bn_terms)

    # Cost is bounded even for an unexpectedly long query.
    assert len(lexical._unicode_search_terms("あ" * 10000 + "。東京工芸大学")) <= 16


def test_unicode_fallback_keeps_late_japanese_term_tenant_scoped(
    client: TestClient, db_session: Session,
):
    alice, ah = _owner(client, "late_jp_a")
    bob, bh = _owner(client, "late_jp_b")
    target = _upload(
        client, ah, "university.md",
        "東京工芸大学の研究室では画像認識の実験を毎週水曜日に行います。",
    )
    private = _upload(
        client, bh, "secret.md",
        "東京工芸大学には非公開の機密情報が保存されています。",
    )
    q = RetrievalQuery(
        user_id=alice,
        text=(
            "これは前置きとしてとても長い文章を書いていますが"
            "ここからが質問の本題になります。東京工芸大学"
        ),
        document_ids=(target, private),
        chunk_roles=("content",),
        top_k=5,
    )
    hits = lexical._fallback_unicode_chunks(db_session, q)
    assert hits
    assert hits[0].document_id == target
    assert all(h.document_id != private for h in hits)
    assert all(h.metadata["lexical_match"] == "unicode_substring" for h in hits)


def test_postgresql_multilingual_fusion_ab_quality_and_latency(
    client: TestClient, db_session: Session, monkeypatch,
):
    """True PostgreSQL lexical A/B on tiny synthetic four-script cases.

    This is NOT an LLM reranker or semantic-model accuracy benchmark, and
    in-process wall times are NOT live network response / token latency.
    """
    owner, header = _owner(client, "ab_quality")
    intruder, intruder_header = _owner(client, "ab_private")
    language_docs = {
        "english": _upload(
            client, header, "english.md",
            "Our support hours are 09:00 to 17:00 every business day.",
        ),
        "japanese": _upload(
            client, header, "japanese.md",
            "東京工芸大学の研究室では画像認識の実験を毎週水曜日に行います。",
        ),
        "bengali": _upload(
            client, header, "bengali.md",
            "返金返金. ফেরতের সময়সীমা পাঁচ কর্মদিবস এবং গ্রাহককে ইমেইল পাঠানো হয়।",
        ),
        "banglish": _upload(
            client, header, "banglish.md",
            "Amader onboarding guide e salary policy niye proshno kora jay.",
        ),
    }
    _upload(client, header, "distractor.md",
            "Our support desk handles refund and onboarding requests.")
    private_id = _upload(
        client, intruder_header, "other-owner.md",
        "東京工芸大学ের গোপন ফেরতের সময়সীমা is not public.",
    )
    queries = {
        "english": "support hours",
        "japanese": "support 東京工芸大学の研究室",
        "bengali": "refund ফেরতের সময়সীমা",
        "banglish": "onboarding guide salary policy",
    }
    cases = []
    for language, question in queries.items():
        relevant = frozenset(db_session.scalars(
            select(DocumentChunk.id).where(
                DocumentChunk.document_id == language_docs[language],
                DocumentChunk.chunk_role == "content",
            )
        ).all())
        assert relevant
        cases.append(RetrievalEvaluationCase(
            query_id=language,
            query=question,
            relevant_chunk_ids=relevant,
        ))

    def run(enabled: bool):
        monkeypatch.setattr(
            settings, "KNOWLEDGE_MULTILINGUAL_UNICODE_FUSION_ENABLED", enabled,
        )
        rankings = {}
        elapsed_ms = []
        by_language_latency: dict[str, list[float]] = {
            name: [] for name in queries
        }
        for _round in range(3):
            for language, question in queries.items():
                started = time.perf_counter()
                hits = lexical.search_lexical_chunks(
                    db_session,
                    RetrievalQuery(
                        user_id=owner, text=question, top_k=5,
                        chunk_roles=("content",),
                    ),
                )
                elapsed = (time.perf_counter() - started) * 1000.0
                elapsed_ms.append(elapsed)
                by_language_latency[language].append(elapsed)
                assert all(hit.document_id != private_id for hit in hits)
                rankings[language] = tuple(hit.chunk_id for hit in hits)
        summaries = {
            k: evaluate_rankings(
                cases=tuple(cases), rankings=rankings, k=k,
            )
            for k in (1, 3)
        }
        latencies = sorted(elapsed_ms)
        per_language_p95 = {
            name: round(sorted(samples)[math.ceil(.95 * len(samples)) - 1], 3)
            for name, samples in by_language_latency.items()
        }
        return rankings, summaries, {
            "n": len(elapsed_ms),
            "p50_ms": round(latencies[math.ceil(.5 * len(latencies)) - 1], 3),
            "p95_ms": round(latencies[math.ceil(.95 * len(latencies)) - 1], 3),
            "per_language_p95_ms": per_language_p95,
        }

    baseline_ranks, baseline, baseline_latency = run(False)
    fused_ranks, fused, fused_latency = run(True)
    # English and Latin-only Banglish must not be degraded by Unicode fusion.
    for language in ("english", "banglish"):
        assert fused_ranks[language] == baseline_ranks[language]
    for language in ("japanese", "bengali"):
        expected = next(c.relevant_chunk_ids for c in cases if c.query_id == language)
        assert any(chunk in expected for chunk in fused_ranks[language])
    assert fused[1].hit_rate_at_k >= baseline[1].hit_rate_at_k
    assert fused[3].mean_ndcg_at_k >= baseline[3].mean_ndcg_at_k

    # Safe aggregate diagnostics: no document content, usernames or tokens.
    report = {
        "label": "synthetic_postgres_lexical_only_not_production",
        "case_count": len(cases),
        "per_language": {
            lang: {
                "baseline_hit_at_1": next(
                    int(case.hit_at_k) for case in baseline[1].cases
                    if case.query_id == lang
                ),
                "fusion_hit_at_1": next(
                    int(case.hit_at_k) for case in fused[1].cases
                    if case.query_id == lang
                ),
                "baseline_ndcg_at_3": next(
                    round(case.ndcg_at_k, 4) for case in baseline[3].cases
                    if case.query_id == lang
                ),
                "fusion_ndcg_at_3": next(
                    round(case.ndcg_at_k, 4) for case in fused[3].cases
                    if case.query_id == lang
                ),
            }
            for lang in queries
        },
        "baseline": {
            "hit_at_1": baseline[1].hit_rate_at_k,
            "mrr_at_3": baseline[3].mrr_at_k,
            "ndcg_at_3": baseline[3].mean_ndcg_at_k,
            "latency": baseline_latency,
        },
        "unicode_fusion": {
            "hit_at_1": fused[1].hit_rate_at_k,
            "mrr_at_3": fused[3].mrr_at_k,
            "ndcg_at_3": fused[3].mean_ndcg_at_k,
            "latency": fused_latency,
        },
    }
    print("AQLYRA_SYNTHETIC_MULTILINGUAL_LEXICAL_AB=" + json.dumps(report))
