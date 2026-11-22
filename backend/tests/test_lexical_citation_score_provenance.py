"""Regression: source citations must not invent cosine similarity for lexical-only retrieval.

Use the real RetrievalHit/evidence-context path and real API schema to ensure
the literal internal placeholder 0.0 never becomes an asserted dense score.
No providers or user data are used in these tests.
"""
import pytest

from app.rag import build_evidence_context
from app.retrieval.types import RetrievalHit
from app.schemas.rag import RAGCitationResponse
from app.services.chat_service import _citation_payload


def sample_hit(*, measured: bool, value: float = 0.86) -> RetrievalHit:
    return RetrievalHit(
        chunk_id="synthetic-chunk",
        document_id="synthetic-owned-doc",
        original_filename="synthetic-policy.md",
        parent_chunk_id=None,
        chunk_role="content",
        chunk_level=0,
        chunk_index=1,
        source_label="Synthetic policy",
        section_path=(),
        content="The fictional policy has twelve leave days per year.",
        start_page=1,
        end_page=1,
        similarity_score=value if measured else 0.0,
        cosine_distance=1.0 - value if measured else 1.0,
        ranking_score=0.42,
        metadata=(
            {"retrieval_mode": "hybrid", "semantic_similarity_available": True}
            if measured
            else {
                "retrieval_mode": "lexical_only",
                "semantic_similarity_available": False,
                "semantic_similarity_score": None,
                "retrieval_sources": ["lexical"],
            }
        ),
    )


def api_citation_from_source(source):
    return RAGCitationResponse(
        source_id=source.source_id,
        chunk_id=source.chunk_id,
        document_id=source.document_id,
        parent_chunk_id=source.parent_chunk_id,
        filename=source.original_filename,
        chunk_role=source.chunk_role,
        chunk_level=source.chunk_level,
        chunk_index=source.chunk_index,
        source_label=source.source_label,
        section_path=list(source.section_path),
        start_page=source.start_page,
        end_page=source.end_page,
        similarity_score=source.similarity_score,
        excerpt=source.content,
        was_truncated=source.was_truncated,
    )


def test_lexical_only_source_is_citable_but_dense_similarity_unknown():
    hit = sample_hit(measured=False)
    evidence = build_evidence_context([hit])
    assert len(evidence.sources) == 1
    source = evidence.sources[0]
    assert source.source_id == "S1"
    assert "twelve leave days" in source.content
    assert source.document_id == hit.document_id
    assert source.similarity_score is None

    citation = api_citation_from_source(source)
    assert citation.model_dump(mode="json")["similarity_score"] is None
    assert _citation_payload(source)["similarity_score"] is None
    assert "[S1]" in evidence.text


@pytest.mark.parametrize("marker", [
    {"retrieval_mode": "lexical_only"},
    {"semantic_similarity_available": False},
])
def test_each_explicit_no_semantic_marker_prevents_score_laundering(marker):
    from dataclasses import replace
    hit = replace(sample_hit(measured=False), metadata=marker)
    source = build_evidence_context([hit]).sources[0]
    assert source.similarity_score is None
    assert _citation_payload(source)["similarity_score"] is None


@pytest.mark.parametrize("actual", [0.0, 0.42, 0.91])
def test_measured_dense_similarity_is_preserved_in_api_and_chat(actual):
    from dataclasses import replace
    hit = replace(sample_hit(measured=True), similarity_score=actual)
    context = build_evidence_context([hit])
    source = context.sources[0]
    assert source.similarity_score == pytest.approx(actual)
    assert api_citation_from_source(source).similarity_score == pytest.approx(actual)
    assert _citation_payload(source)["similarity_score"] == pytest.approx(actual)
    assert context.sources[0].chunk_id == hit.chunk_id


def test_uncategorized_dense_hit_retains_original_metric():
    from dataclasses import replace
    hit = replace(sample_hit(measured=True), metadata={})
    source = build_evidence_context([hit]).sources[0]
    assert source.similarity_score == pytest.approx(0.86)
