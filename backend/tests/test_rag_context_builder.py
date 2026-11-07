from dataclasses import dataclass, field
from typing import Any

from app.rag import (
    EvidenceContextConfig,
    build_evidence_context,
)


@dataclass(frozen=True, slots=True)
class FakeRetrievalHit:
    chunk_id: str
    document_id: str
    original_filename: str
    content: str
    similarity_score: float

    parent_chunk_id: str | None = None
    chunk_role: str = "content"
    chunk_level: int = 0
    chunk_index: int = 0
    source_label: str = "Section"
    section_path: tuple[str, ...] = ()
    start_page: int | None = None
    end_page: int | None = None
    metadata: dict[str, Any] = field(
        default_factory=dict
    )


def test_context_orders_sources_by_similarity(
) -> None:
    hits = [
        FakeRetrievalHit(
            chunk_id="chunk-low",
            document_id="document-1",
            original_filename="guide.md",
            content="Lower-ranked evidence.",
            similarity_score=0.70,
            chunk_index=2,
        ),
        FakeRetrievalHit(
            chunk_id="chunk-high",
            document_id="document-1",
            original_filename="guide.md",
            content="Higher-ranked evidence.",
            similarity_score=0.95,
            chunk_index=1,
        ),
    ]

    context = build_evidence_context(
        hits
    )

    assert context.has_evidence is True
    assert len(context.sources) == 2

    assert (
        context.sources[0].source_id
        == "S1"
    )

    assert (
        context.sources[0].chunk_id
        == "chunk-high"
    )

    assert (
        context.sources[1].source_id
        == "S2"
    )

    assert context.text.index("[S1]") < (
        context.text.index("[S2]")
    )


def test_context_removes_duplicate_content(
) -> None:
    hits = [
        FakeRetrievalHit(
            chunk_id="chunk-1",
            document_id="document-1",
            original_filename="a.md",
            content=(
                "The same retrieved evidence."
            ),
            similarity_score=0.90,
        ),
        FakeRetrievalHit(
            chunk_id="chunk-2",
            document_id="document-2",
            original_filename="b.md",
            content=(
                "  The same retrieved "
                "evidence.  "
            ),
            similarity_score=0.80,
        ),
    ]

    context = build_evidence_context(
        hits
    )

    assert len(context.sources) == 1
    assert context.sources[0].chunk_id == (
        "chunk-1"
    )

    assert context.skipped_count == 1


def test_context_removes_redundant_parent_summary(
) -> None:
    hits = [
        FakeRetrievalHit(
            chunk_id="parent-summary",
            document_id="document-1",
            original_filename="manual.md",
            content="Extractive parent summary.",
            similarity_score=0.95,
            chunk_role="summary",
            chunk_level=1,
        ),
        FakeRetrievalHit(
            chunk_id="child-content",
            document_id="document-1",
            original_filename="manual.md",
            content=(
                "Detailed child evidence."
            ),
            similarity_score=0.90,
            parent_chunk_id="parent-summary",
            chunk_role="content",
            chunk_level=0,
        ),
    ]

    context = build_evidence_context(
        hits
    )

    assert len(context.sources) == 1

    assert (
        context.sources[0].chunk_id
        == "child-content"
    )

    assert context.skipped_count == 1


def test_context_respects_token_budget(
) -> None:
    long_content = "evidence " * 500

    context = build_evidence_context(
        [
            FakeRetrievalHit(
                chunk_id="chunk-long",
                document_id="document-1",
                original_filename=(
                    "long-document.md"
                ),
                content=long_content,
                similarity_score=0.99,
            )
        ],
        config=EvidenceContextConfig(
            max_context_tokens=60,
            max_source_tokens=40,
            max_sources=2,
        ),
    )

    assert context.has_evidence is True

    assert (
        context.estimated_tokens
        <= 60
    )

    assert (
        context.sources[0].was_truncated
        is True
    )

    assert context.was_truncated is True


def test_context_applies_role_and_similarity_filters(
) -> None:
    hits = [
        FakeRetrievalHit(
            chunk_id="valid-content",
            document_id="document-1",
            original_filename="valid.md",
            content="Strong content evidence.",
            similarity_score=0.90,
            chunk_role="content",
        ),
        FakeRetrievalHit(
            chunk_id="weak-content",
            document_id="document-1",
            original_filename="weak.md",
            content="Weak evidence.",
            similarity_score=0.30,
            chunk_role="content",
        ),
        FakeRetrievalHit(
            chunk_id="summary",
            document_id="document-1",
            original_filename="summary.md",
            content="Summary evidence.",
            similarity_score=0.95,
            chunk_role="summary",
        ),
    ]

    context = build_evidence_context(
        hits,
        config=EvidenceContextConfig(
            max_context_tokens=200,
            max_source_tokens=100,
            max_sources=5,
            min_similarity=0.50,
            include_roles=("content",),
        ),
    )

    assert len(context.sources) == 1

    assert (
        context.sources[0].chunk_id
        == "valid-content"
    )

    assert context.skipped_count == 2


def test_context_enforces_max_sources(
) -> None:
    hits = [
        FakeRetrievalHit(
            chunk_id=f"chunk-{index}",
            document_id="document-1",
            original_filename="sources.md",
            content=f"Evidence number {index}.",
            similarity_score=(
                0.95 - index * 0.01
            ),
            chunk_index=index,
        )
        for index in range(4)
    ]

    context = build_evidence_context(
        hits,
        config=EvidenceContextConfig(
            max_context_tokens=500,
            max_source_tokens=100,
            max_sources=2,
        ),
    )

    assert len(context.sources) == 2
    assert context.skipped_count == 2
    assert context.was_truncated is True


def test_balanced_packing_preserves_three_citations_with_small_budget() -> None:
    hits = [
        FakeRetrievalHit(
            chunk_id=f"evidence-{index}",
            document_id=f"document-{index}",
            original_filename=f"source-{index}.md",
            content=(f"Unique evidence {index}. " * 130),
            similarity_score=0.95 - index * 0.05,
        )
        for index in range(3)
    ]
    legacy = build_evidence_context(
        hits,
        config=EvidenceContextConfig(
            max_context_tokens=160,
            max_source_tokens=110,
            max_sources=3,
        ),
    )
    balanced = build_evidence_context(
        hits,
        config=EvidenceContextConfig(
            max_context_tokens=160,
            max_source_tokens=110,
            max_sources=3,
            balance_source_budget=True,
        ),
    )

    assert len(legacy.sources) < 3
    assert len(balanced.sources) == 3
    assert [source.chunk_id for source in balanced.sources] == [
        "evidence-0", "evidence-1", "evidence-2",
    ]
    assert [source.source_id for source in balanced.sources] == [
        "S1", "S2", "S3",
    ]
    assert balanced.estimated_tokens <= 160
    assert all(source.was_truncated for source in balanced.sources)


def test_balanced_packing_keeps_full_single_source_and_multilingual_text() -> None:
    hit = FakeRetrievalHit(
        chunk_id="bangla-japanese",
        document_id="document-1",
        original_filename="notes.txt",
        content="বাংলাদেশে শিক্ষা এবং 日本語の学習資料।",
        similarity_score=0.92,
    )
    context = build_evidence_context(
        [hit],
        config=EvidenceContextConfig(
            max_context_tokens=120,
            max_source_tokens=100,
            balance_source_budget=True,
        ),
    )

    assert len(context.sources) == 1
    assert context.sources[0].content == hit.content
    assert context.sources[0].was_truncated is False
    assert context.estimated_tokens <= 120


def test_balanced_packing_skips_unfeasible_reservation() -> None:
    hits = [
        FakeRetrievalHit(
            chunk_id=f"evidence-{index}",
            document_id=f"document-{index}",
            original_filename="notes.txt",
            content="Important factual evidence. " * 80,
            similarity_score=0.9 - index * 0.01,
        )
        for index in range(5)
    ]
    context = build_evidence_context(
        hits,
        config=EvidenceContextConfig(
            max_context_tokens=48,
            max_source_tokens=40,
            max_sources=5,
            balance_source_budget=True,
        ),
    )
    assert context.has_evidence
    assert context.estimated_tokens <= 48
    assert context.sources[0].chunk_id == "evidence-0"


def test_empty_hits_return_empty_context(
) -> None:
    context = build_evidence_context(
        []
    )

    assert context.has_evidence is False
    assert context.text == ""
    assert context.sources == ()
    assert context.estimated_tokens == 0
    assert context.skipped_count == 0
    assert context.was_truncated is False
