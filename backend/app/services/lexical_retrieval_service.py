import re
from dataclasses import dataclass, field, replace
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

from app.config.settings import settings
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.retrieval import RetrievalQuery
from app.services.retrieval_exclusions import permitted_retrieval_document


_TEXT_SEARCH_CONFIG = literal_column(
    "'simple'::regconfig"
)

_MAX_QUERY_TERMS = 32

# The lexical path must work even when the 384D semantic worker is rate
# limited. Common English question framing can otherwise dominate OR-based
# FTS rankings for short document questions ("What are ... support hours?").
# Limit this list to function words; never omit topical terms, names, dates,
# Japanese/Bengali characters or a query containing only these terms.
_ENGLISH_QUESTION_FILLER = frozenset({
    "a", "an", "are", "am", "be", "been", "can", "could", "did",
    "do", "does", "for", "from", "how", "i", "in", "is", "it",
    "its", "me", "my", "of", "on", "our", "please", "the",
    "their", "to", "was", "were", "what", "when", "where",
    "which", "who", "why", "will", "would", "you", "your",
})

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
    """Retain informative words before constructing PostgreSQL FTS.

    With the semantic provider unavailable, OR-ing all words in a question
    such as "What are Pilot Orion's support hours?" causes weak documents
    matching "what", "are" or "'s" to outrank the correct source.
    """
    terms: list[str] = []
    seen: set[str] = set()

    for raw_term in text.split():
        term = raw_term.strip(_STRIP_CHARACTERS)
        if not term:
            continue

        # English possessives should match the document's proper noun
        # "Orion", not a PostgreSQL expression that also requires "s".
        if term.casefold().endswith(("\u0027s", "\u2019s")) and len(term) > 2:
            term = term[:-2]
        normalized = term.casefold()

        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        terms.append(term)

        if len(terms) >= _MAX_QUERY_TERMS:
            break

    informative = [
        term for term in terms
        if term.casefold() not in _ENGLISH_QUESTION_FILLER
    ]

    # Preserve previous behavior for a query containing only stopwords
    # rather than turning it into a silent empty result.
    return tuple(informative or terms)


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
            permitted_retrieval_document(),
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



def _fuse_multilingual_lexical_hits(
    *,
    fts_hits: list[LexicalRetrievalHit],
    unicode_hits: list[LexicalRetrievalHit],
    top_k: int,
) -> list[LexicalRetrievalHit]:
    """Fuse two real lexical rankings without mixing incomparable raw scores.

    The Unicode channel is weighted slightly higher only for script-bearing
    queries. FTS score and Unicode n-gram counts remain their original
    measured values; metadata reports the RRF ordering score separately.
    No vectors, citations, user content, or synthetic matches are created.
    """
    if not fts_hits:
        return unicode_hits[:top_k]
    if not unicode_hits:
        return fts_hits[:top_k]

    fts_rank = {
        hit.chunk_id: index
        for index, hit in enumerate(fts_hits, start=1)
    }
    unicode_rank = {
        hit.chunk_id: index
        for index, hit in enumerate(unicode_hits, start=1)
    }
    hits_by_id = {
        hit.chunk_id: hit
        for hit in unicode_hits
    }
    # Preserve the exact FTS lexical_score if both channels matched.
    hits_by_id.update({
        hit.chunk_id: hit
        for hit in fts_hits
    })

    ranked: list[tuple[float, int, str, LexicalRetrievalHit]] = []
    for chunk_id, hit in hits_by_id.items():
        lexical_position = fts_rank.get(chunk_id)
        unicode_position = unicode_rank.get(chunk_id)
        score = (
            (1.0 / (60 + lexical_position) if lexical_position else 0.0)
            + (1.15 / (60 + unicode_position) if unicode_position else 0.0)
        )
        best_rank = min(
            rank
            for rank in (lexical_position, unicode_position)
            if rank is not None
        )
        channels = []
        if lexical_position is not None:
            channels.append("fts")
        if unicode_position is not None:
            channels.append("unicode_substring")
        metadata = dict(hit.metadata)
        metadata.update({
            "lexical_channels": channels,
            "multilingual_rrf_score": score,
        })
        ranked.append((
            -score,
            best_rank,
            str(chunk_id),
            replace(hit, metadata=metadata),
        ))

    ranked.sort(key=lambda entry: entry[:3])
    return [entry[3] for entry in ranked[:top_k]]


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
            permitted_retrieval_document(),
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

    if (
        hits
        and settings.KNOWLEDGE_MULTILINGUAL_UNICODE_FUSION_ENABLED
        and _unicode_search_terms(query.text)
    ):
        # FTS can match an incidental English term while missing the
        # relevant Japanese/Bengali phrase. Keep both tenant-scoped
        # candidate lists rather than suppressing Unicode retrieval.
        unicode_hits = _fallback_unicode_chunks(db=db, query=query)
        return _fuse_multilingual_lexical_hits(
            fts_hits=hits,
            unicode_hits=unicode_hits,
            top_k=query.top_k,
        )

    return hits