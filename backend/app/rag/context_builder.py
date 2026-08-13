import hashlib
import re
from collections.abc import Sequence

from app.rag.types import (
    EvidenceContext,
    EvidenceContextConfig,
    EvidenceSource,
    RetrievalEvidence,
)


_TOKEN_PATTERN = re.compile(
    r"[A-Za-z0-9]+(?:['’-][A-Za-z0-9]+)*"
    r"|[\u3040-\u30ff]"
    r"|[\u3400-\u9fff]"
    r"|[\uac00-\ud7af]"
    r"|[^\s]",
    flags=re.UNICODE,
)


def estimate_context_tokens(text: str) -> int:
    """
    Return a deterministic multilingual token estimate.

    This is intentionally provider-independent. It is used for
    context budgeting, not provider billing.
    """

    if not text:
        return 0

    return len(
        _TOKEN_PATTERN.findall(text)
    )


def _normalize_for_hash(text: str) -> str:
    return re.sub(
        r"\s+",
        " ",
        text,
    ).strip()


def _content_fingerprint(text: str) -> str:
    normalized = _normalize_for_hash(text)

    return hashlib.sha256(
        normalized.encode("utf-8")
    ).hexdigest()


def _truncate_to_token_limit(
    text: str,
    max_tokens: int,
) -> tuple[str, bool]:
    cleaned = text.strip()

    if not cleaned:
        return "", False

    if estimate_context_tokens(cleaned) <= max_tokens:
        return cleaned, False

    if max_tokens == 1:
        return "…", True

    content_budget = max_tokens - 1

    low = 0
    high = len(cleaned)
    best = ""

    while low <= high:
        middle = (low + high) // 2
        candidate = cleaned[:middle].rstrip()

        token_count = estimate_context_tokens(
            candidate
        )

        if token_count <= content_budget:
            best = candidate
            low = middle + 1
        else:
            high = middle - 1

    if not best:
        return "…", True

    result = f"{best}…"

    while (
        estimate_context_tokens(result)
        > max_tokens
        and best
    ):
        best = best[:-1].rstrip()
        result = f"{best}…"

    return result, True


def _format_page_location(
    start_page: int | None,
    end_page: int | None,
) -> str | None:
    if start_page is None:
        return None

    if (
        end_page is None
        or end_page == start_page
    ):
        return f"page {start_page}"

    return (
        f"pages {start_page}-{end_page}"
    )


def _build_source_header(
    *,
    source_id: str,
    filename: str,
    source_label: str,
    section_path: tuple[str, ...],
    start_page: int | None,
    end_page: int | None,
) -> str:
    locations: list[str] = []

    if source_label.strip():
        locations.append(
            source_label.strip()
        )

    if section_path:
        locations.append(
            " > ".join(section_path)
        )

    page_location = _format_page_location(
        start_page=start_page,
        end_page=end_page,
    )

    if page_location:
        locations.append(page_location)

    location_text = " | ".join(locations)

    if location_text:
        return (
            f"[{source_id}] "
            f"{filename} — {location_text}"
        )

    return f"[{source_id}] {filename}"


def _ranking_value(
    hit: RetrievalEvidence,
) -> float:
    ranking_score = getattr(
        hit,
        "ranking_score",
        None,
    )

    if ranking_score is not None:
        return float(
            ranking_score
        )

    return float(
        hit.similarity_score
    )


def _sort_key(
    hit: RetrievalEvidence,
) -> tuple[
    float,
    str,
    int,
    str,
]:
    return (
        -_ranking_value(hit),
        str(hit.document_id),
        int(hit.chunk_index),
        str(hit.chunk_id),
    )


def _prepare_candidates(
    hits: Sequence[RetrievalEvidence],
    config: EvidenceContextConfig,
) -> tuple[
    list[RetrievalEvidence],
    int,
]:
    skipped_count = 0
    filtered: list[RetrievalEvidence] = []

    allowed_roles = set(
        config.include_roles
    )

    for hit in hits:
        content = hit.content.strip()

        if not content:
            skipped_count += 1
            continue

        if hit.chunk_role not in allowed_roles:
            skipped_count += 1
            continue

        if (
            float(hit.similarity_score)
            < config.min_similarity
        ):
            skipped_count += 1
            continue

        filtered.append(hit)

    ordered = sorted(
        filtered,
        key=_sort_key,
    )

    unique_hits: list[RetrievalEvidence] = []
    seen_content: set[str] = set()

    for hit in ordered:
        fingerprint = _content_fingerprint(
            hit.content
        )

        if fingerprint in seen_content:
            skipped_count += 1
            continue

        seen_content.add(fingerprint)
        unique_hits.append(hit)

    child_parent_ids = {
        str(hit.parent_chunk_id)
        for hit in unique_hits
        if hit.parent_chunk_id is not None
    }

    candidates: list[RetrievalEvidence] = []

    for hit in unique_hits:
        is_redundant_parent = (
            hit.chunk_role == "summary"
            and str(hit.chunk_id)
            in child_parent_ids
        )

        if is_redundant_parent:
            skipped_count += 1
            continue

        candidates.append(hit)

    return candidates, skipped_count


def build_evidence_context(
    hits: Sequence[RetrievalEvidence],
    config: EvidenceContextConfig | None = None,
) -> EvidenceContext:
    active_config = (
        config
        or EvidenceContextConfig()
    )

    candidates, skipped_count = (
        _prepare_candidates(
            hits=hits,
            config=active_config,
        )
    )

    if not candidates:
        return EvidenceContext(
            text="",
            sources=(),
            estimated_tokens=0,
            skipped_count=skipped_count,
            was_truncated=False,
        )

    blocks: list[str] = []
    sources: list[EvidenceSource] = []
    used_tokens = 0
    was_truncated = False

    for candidate_index, hit in enumerate(
        candidates
    ):
        if len(sources) >= active_config.max_sources:
            skipped_count += (
                len(candidates)
                - candidate_index
            )
            was_truncated = True
            break

        source_id = (
            f"S{len(sources) + 1}"
        )

        section_path = tuple(
            str(value).strip()
            for value in hit.section_path
            if str(value).strip()
        )

        header = _build_source_header(
            source_id=source_id,
            filename=(
                hit.original_filename.strip()
                or "unknown-document"
            ),
            source_label=hit.source_label,
            section_path=section_path,
            start_page=hit.start_page,
            end_page=hit.end_page,
        )

        remaining_budget = (
            active_config.max_context_tokens
            - used_tokens
        )

        separator_tokens = (
            estimate_context_tokens("\n\n")
            if blocks
            else 0
        )

        header_tokens = (
            estimate_context_tokens(
                f"{header}\n"
            )
        )

        available_content_tokens = (
            remaining_budget
            - separator_tokens
            - header_tokens
        )

        if available_content_tokens < 1:
            skipped_count += (
                len(candidates)
                - candidate_index
            )
            was_truncated = True
            break

        content_limit = min(
            active_config.max_source_tokens,
            available_content_tokens,
        )

        content, source_was_truncated = (
            _truncate_to_token_limit(
                text=hit.content,
                max_tokens=content_limit,
            )
        )

        if not content:
            skipped_count += 1
            continue

        block = f"{header}\n{content}"

        block_tokens = (
            estimate_context_tokens(block)
        )

        total_candidate_tokens = (
            used_tokens
            + separator_tokens
            + block_tokens
        )

        if (
            total_candidate_tokens
            > active_config.max_context_tokens
        ):
            skipped_count += (
                len(candidates)
                - candidate_index
            )
            was_truncated = True
            break

        blocks.append(block)
        used_tokens = total_candidate_tokens

        sources.append(
            EvidenceSource(
                source_id=source_id,
                chunk_id=str(hit.chunk_id),
                document_id=str(
                    hit.document_id
                ),
                original_filename=(
                    hit.original_filename
                ),
                parent_chunk_id=(
                    str(hit.parent_chunk_id)
                    if hit.parent_chunk_id
                    is not None
                    else None
                ),
                chunk_role=hit.chunk_role,
                chunk_level=hit.chunk_level,
                chunk_index=hit.chunk_index,
                source_label=(
                    hit.source_label
                ),
                section_path=section_path,
                start_page=hit.start_page,
                end_page=hit.end_page,
                similarity_score=float(
                    hit.similarity_score
                ),
                content=content,
                was_truncated=(
                    source_was_truncated
                ),
            )
        )

        if source_was_truncated:
            was_truncated = True

    context_text = "\n\n".join(
        blocks
    )

    return EvidenceContext(
        text=context_text,
        sources=tuple(sources),
        estimated_tokens=(
            estimate_context_tokens(
                context_text
            )
        ),
        skipped_count=skipped_count,
        was_truncated=was_truncated,
    )
