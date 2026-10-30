import re
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import (
    func,
    case,
    literal_column,
    select,
    or_,
    literal,
)
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.retrieval import RetrievalQuery


_TEXT_SEARCH_CONFIG = literal_column(
    "'simple'::regconfig"
)

_MAX_QUERY_TERMS = 32

_STRIP_CHARACTERS = (
    ".,;:!?()[]{}<>"
    "\"'`“”‘’"
)


@dataclass(frozen=True, slots=True)
class LexicalRetrievalHit:
    chunk_id: str
    document_id: str
    original_filename: str
    parent_chunk_id: str | None

    chunk_role: str
    chunk_level: int
    chunk_index: int

    source_label: str
    section_path: tuple[str, ...]

    content: str

    start_page: int | None
    end_page: int | None

    lexical_score: float

    metadata: dict[str, Any] = field(
        default_factory=dict
    )


def _extract_query_terms(
    text: str,
) -> tuple[str, ...]:
    terms: list[str] = []
    seen: set[str] = set()

    for raw_term in text.split():
        term = raw_term.strip(
            _STRIP_CHARACTERS
        )

        if not term:
            continue

        normalized = term.casefold()

        if normalized in seen:
            continue

        seen.add(normalized)
        terms.append(term)

        if len(terms) >= _MAX_QUERY_TERMS:
            break

    return tuple(terms)


def _build_lexical_query(
    text: str,
):
    terms = _extract_query_terms(text)

    if not terms:
        return None

    query_expression = func.plainto_tsquery(
        _TEXT_SEARCH_CONFIG,
        terms[0],
    )

    for term in terms[1:]:
        next_query = func.plainto_tsquery(
            _TEXT_SEARCH_CONFIG,
            term,
        )

        query_expression = (
            query_expression.op("||")(
                next_query
            )
        )

    return query_expression


_UNSEGMENTED_SCRIPT = re.compile(
    r"[\u3040-\u30ff\u3400-\u9fff]{2,}|[\u0980-\u09ff]{3,}"
)


def _unicode_search_terms(text: str) -> tuple[str, ...]:
    """Small bound for CJK and Bangla where PostgreSQL 'simple' FTS
    cannot reliably tokenize document/question text into the same words.
    """
    values: list[str] = []
    for match in _UNSEGMENTED_SCRIPT.finditer(text):
        candidate = match.group(0)
        if "\u0980" <= candidate[0] <= "\u09ff":
            values.append(candidate[:36])
            if len(candidate) > 5:
                values.append(candidate[:5])
        elif len(candidate) <= 3:
            values.append(candidate)
        else:
            values.extend(candidate[i : i + 3] for i in range(len(candidate) - 2))
        if len(values) >= 16:
            break
    return tuple(dict.fromkeys(values[:16]))


def _fallback_unicode_chunks(db: Session, query: RetrievalQuery) -> list[LexicalRetrievalHit]:
    terms = _unicode_search_terms(query.text)
    if not terms:
        return []
    # Both filename/document_id filters AND tenant+status checks apply
    # BEFORE the content match. Never search other users' chunks.
    content = DocumentChunk.embedding_content
    conditions = []
    for term in terms:
        escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        conditions.append(content.ilike(f"%{escaped}%", escape="\\"))
    # Rank by bounded Unicode n-gram coverage instead of arbitrary
    # chunk insertion order; lexical and vector scores remain distinct.
    unicode_score = sum(
        (case((matched, 1.0), else_=0.0) for matched in conditions),
        literal(0.0),
    )
    statement = (
        select(DocumentChunk, Document, unicode_score.label("lexical_score"))
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(
            Document.user_id == query.user_id,
            Document.status == "ready",
            or_(*conditions),
        )
    )
    if query.document_ids:
        statement = statement.where(Document.id.in_(query.document_ids))
    if query.chunk_roles:
        statement = statement.where(DocumentChunk.chunk_role.in_(query.chunk_roles))
    rows = db.execute(
        statement.order_by(
            unicode_score.desc(),
            DocumentChunk.chunk_index.asc(),
            DocumentChunk.id.asc(),
        ).limit(query.top_k)
    ).all()
    return [
        LexicalRetrievalHit(
            chunk_id=chunk.id,
            document_id=document.id,
            original_filename=document.original_filename,
            parent_chunk_id=chunk.parent_chunk_id,
            chunk_role=chunk.chunk_role,
            chunk_level=chunk.chunk_level,
            chunk_index=chunk.chunk_index,
            source_label=chunk.source_label,
            section_path=tuple(chunk.section_path or []),
            content=chunk.content,
            start_page=chunk.start_page,
            end_page=chunk.end_page,
            lexical_score=float(score),
            metadata={
                **(chunk.chunk_metadata or {}),
                "lexical_match": "unicode_substring",
            },
        )
        for chunk, document, score in rows
    ]


def search_lexical_chunks(
    db: Session,
    query: RetrievalQuery,
) -> list[LexicalRetrievalHit]:
    """
    Search document chunks using PostgreSQL
    full-text retrieval.

    The lexical path is deliberately separate from
    dense-vector retrieval. Hybrid rank fusion is
    performed by a later orchestration layer.
    """

    lexical_query = _build_lexical_query(
        query.text
    )

    if lexical_query is None:
        return []

    search_vector = func.to_tsvector(
        _TEXT_SEARCH_CONFIG,
        DocumentChunk.embedding_content,
    )

    lexical_score = func.ts_rank_cd(
        search_vector,
        lexical_query,
    )

    statement = (
        select(
            DocumentChunk,
            Document,
            lexical_score.label(
                "lexical_score"
            ),
        )
        .join(
            Document,
            Document.id
            == DocumentChunk.document_id,
        )
        .where(
            Document.user_id
            == query.user_id,
            Document.status
            == "ready",
            search_vector.op("@@")(
                lexical_query
            ),
        )
    )

    if query.document_ids:
        statement = statement.where(
            Document.id.in_(
                query.document_ids
            )
        )

    if query.chunk_roles:
        statement = statement.where(
            DocumentChunk.chunk_role.in_(
                query.chunk_roles
            )
        )

    statement = (
        statement
        .order_by(
            lexical_score.desc(),
            DocumentChunk.chunk_index.asc(),
            DocumentChunk.id.asc(),
        )
        .limit(query.top_k)
    )

    rows = db.execute(statement).all()
    if not rows and _unicode_search_terms(query.text):
        return _fallback_unicode_chunks(db=db, query=query)

    hits: list[LexicalRetrievalHit] = []

    for chunk, document, score in rows:
        hits.append(
            LexicalRetrievalHit(
                chunk_id=chunk.id,
                document_id=document.id,
                original_filename=(
                    document.original_filename
                ),
                parent_chunk_id=(
                    chunk.parent_chunk_id
                ),
                chunk_role=chunk.chunk_role,
                chunk_level=chunk.chunk_level,
                chunk_index=chunk.chunk_index,
                source_label=(
                    chunk.source_label
                ),
                section_path=tuple(
                    chunk.section_path or []
                ),
                content=chunk.content,
                start_page=chunk.start_page,
                end_page=chunk.end_page,
                lexical_score=float(
                    score or 0.0
                ),
                metadata=dict(
                    chunk.chunk_metadata or {}
                ),
            )
        )

    return hits