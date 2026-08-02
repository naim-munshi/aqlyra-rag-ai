import hashlib
import re
import uuid
from dataclasses import dataclass
from typing import Sequence

from app.chunking.types import (
    ChunkDraft,
    ChunkingConfig,
    ChunkRole,
    ChunkSource,
)


_TOKEN_PATTERN = re.compile(
    r"[A-Za-z0-9]+(?:['’-][A-Za-z0-9]+)*"
    r"|[\u3040-\u30ff]"
    r"|[\u3400-\u9fff]"
    r"|[\uac00-\ud7af]"
    r"|[^\s]",
    flags=re.UNICODE,
)

_SENTENCE_BOUNDARY_PATTERN = re.compile(
    r"[.!?。！？]+[\"'”’）)\]]*"
    r"|\n{2,}",
    flags=re.UNICODE,
)


@dataclass(frozen=True, slots=True)
class _TextSpan:
    start: int
    end: int
    token_count: int


def estimate_tokens(text: str) -> int:
    return len(
        _TOKEN_PATTERN.findall(text)
    )


def _count_words(text: str) -> int:
    return len(
        re.findall(
            r"[A-Za-z0-9]+(?:['’-][A-Za-z0-9]+)*"
            r"|[\u3040-\u30ff]"
            r"|[\u3400-\u9fff]"
            r"|[\uac00-\ud7af]",
            text,
            flags=re.UNICODE,
        )
    )


def _hash_content(content: str) -> str:
    return hashlib.sha256(
        content.encode("utf-8")
    ).hexdigest()


def _trim_span(
    text: str,
    start: int,
    end: int,
) -> tuple[int, int]:
    while (
        start < end
        and text[start].isspace()
    ):
        start += 1

    while (
        end > start
        and text[end - 1].isspace()
    ):
        end -= 1

    return start, end


def _sentence_spans(
    text: str,
) -> list[_TextSpan]:
    spans: list[_TextSpan] = []
    cursor = 0

    for match in (
        _SENTENCE_BOUNDARY_PATTERN.finditer(text)
    ):
        end = match.end()

        start, trimmed_end = _trim_span(
            text=text,
            start=cursor,
            end=end,
        )

        if start < trimmed_end:
            content = text[start:trimmed_end]

            spans.append(
                _TextSpan(
                    start=start,
                    end=trimmed_end,
                    token_count=estimate_tokens(
                        content
                    ),
                )
            )

        cursor = end

    start, end = _trim_span(
        text=text,
        start=cursor,
        end=len(text),
    )

    if start < end:
        content = text[start:end]

        spans.append(
            _TextSpan(
                start=start,
                end=end,
                token_count=estimate_tokens(
                    content
                ),
            )
        )

    if not spans and text.strip():
        start, end = _trim_span(
            text=text,
            start=0,
            end=len(text),
        )

        spans.append(
            _TextSpan(
                start=start,
                end=end,
                token_count=estimate_tokens(
                    text[start:end]
                ),
            )
        )

    return spans


def _split_long_span(
    text: str,
    span: _TextSpan,
    max_tokens: int,
) -> list[_TextSpan]:
    if span.token_count <= max_tokens:
        return [span]

    relative_text = text[
        span.start:span.end
    ]

    token_matches = list(
        _TOKEN_PATTERN.finditer(
            relative_text
        )
    )

    if not token_matches:
        return [span]

    pieces: list[_TextSpan] = []

    for token_start in range(
        0,
        len(token_matches),
        max_tokens,
    ):
        token_end = min(
            token_start + max_tokens,
            len(token_matches),
        )

        first_token = token_matches[
            token_start
        ]

        last_token = token_matches[
            token_end - 1
        ]

        piece_start = (
            span.start
            + first_token.start()
        )

        piece_end = (
            span.start
            + last_token.end()
        )

        piece_start, piece_end = _trim_span(
            text=text,
            start=piece_start,
            end=piece_end,
        )

        if piece_start >= piece_end:
            continue

        pieces.append(
            _TextSpan(
                start=piece_start,
                end=piece_end,
                token_count=token_end
                - token_start,
            )
        )

    return pieces


def _prepare_spans(
    text: str,
    max_tokens: int,
) -> list[_TextSpan]:
    prepared: list[_TextSpan] = []

    for span in _sentence_spans(text):
        prepared.extend(
            _split_long_span(
                text=text,
                span=span,
                max_tokens=max_tokens,
            )
        )

    return prepared


def _adaptive_target_tokens(
    source: ChunkSource,
    config: ChunkingConfig,
) -> int:
    total_tokens = estimate_tokens(
        source.content
    )

    if source.unit_type == "sheet":
        target = 220

    elif source.unit_type == "page":
        target = 380

    elif source.metadata.get("heading"):
        target = 300

    else:
        target = (
            config.default_target_tokens
        )

    if total_tokens > 2500:
        target += 80

    elif total_tokens < 300:
        target = min(
            target,
            260,
        )

    return max(
        config.min_chunk_tokens,
        min(
            target,
            config.max_chunk_tokens,
        ),
    )


def _build_windows(
    spans: Sequence[_TextSpan],
    target_tokens: int,
    min_tokens: int,
    max_tokens: int,
    overlap_tokens: int,
) -> list[tuple[int, int]]:
    if not spans:
        return []

    windows: list[tuple[int, int]] = []
    start_index = 0

    while start_index < len(spans):
        end_index = start_index
        current_tokens = 0

        while end_index < len(spans):
            span_tokens = spans[
                end_index
            ].token_count

            candidate_tokens = (
                current_tokens
                + span_tokens
            )

            if (
                end_index > start_index
                and candidate_tokens
                > max_tokens
            ):
                break

            if (
                end_index > start_index
                and candidate_tokens
                > target_tokens
                and current_tokens
                >= min_tokens
            ):
                break

            current_tokens = (
                candidate_tokens
            )

            end_index += 1

            if (
                current_tokens
                >= target_tokens
            ):
                break

        if end_index == start_index:
            end_index += 1

        windows.append(
            (
                start_index,
                end_index,
            )
        )

        if end_index >= len(spans):
            break

        next_start = end_index
        accumulated_overlap = 0

        while (
            next_start
            > start_index + 1
            and accumulated_overlap
            < overlap_tokens
        ):
            next_start -= 1

            accumulated_overlap += (
                spans[
                    next_start
                ].token_count
            )

        if next_start <= start_index:
            next_start = (
                start_index + 1
            )

        start_index = next_start

    return windows


def _section_path(
    source: ChunkSource,
) -> tuple[str, ...]:
    metadata_path = source.metadata.get(
        "section_path"
    )

    if isinstance(
        metadata_path,
        (list, tuple),
    ):
        cleaned_path = tuple(
            str(value).strip()
            for value in metadata_path
            if str(value).strip()
        )

        if cleaned_path:
            return cleaned_path

    heading = source.metadata.get(
        "heading"
    )

    if heading:
        return (
            str(heading).strip(),
        )

    if source.source_label.strip():
        return (
            source.source_label.strip(),
        )

    return ()


def _page_range(
    source: ChunkSource,
) -> tuple[int | None, int | None]:
    if source.unit_type == "page":
        return (
            source.unit_index,
            source.unit_index,
        )

    page_number = source.metadata.get(
        "page_number"
    )

    if isinstance(page_number, int):
        return (
            page_number,
            page_number,
        )

    start_page = source.metadata.get(
        "start_page"
    )

    end_page = source.metadata.get(
        "end_page"
    )

    if (
        isinstance(start_page, int)
        and isinstance(end_page, int)
    ):
        return (
            start_page,
            end_page,
        )

    return None, None


def _embedding_content(
    *,
    source: ChunkSource,
    section_path: tuple[str, ...],
    content: str,
    role: ChunkRole,
) -> str:
    context_lines = [
        f"Document: {source.document_label}",
        f"Source: {source.source_label}",
        f"Chunk role: {role}",
    ]

    if section_path:
        context_lines.append(
            "Section: "
            + " > ".join(section_path)
        )

    return (
        "\n".join(context_lines)
        + "\n\n"
        + content
    )


def _stable_chunk_id(
    *,
    source: ChunkSource,
    strategy_version: str,
    role: ChunkRole,
    local_index: int,
) -> str:
    identifier = (
        f"{source.document_id}:"
        f"{source.unit_id}:"
        f"{strategy_version}:"
        f"{role}:"
        f"{local_index}"
    )

    return str(
        uuid.uuid5(
            uuid.NAMESPACE_URL,
            identifier,
        )
    )


def _extract_parent_summary(
    content: str,
    token_limit: int,
) -> str:
    token_matches = list(
        _TOKEN_PATTERN.finditer(content)
    )

    if len(token_matches) <= token_limit:
        return content.strip()

    final_token = token_matches[
        token_limit - 1
    ]

    summary = content[
        :final_token.end()
    ].strip()

    return summary + "…"


def build_chunks(
    sources: Sequence[ChunkSource],
    config: ChunkingConfig | None = None,
) -> list[ChunkDraft]:
    active_config = (
        config
        or ChunkingConfig()
    )

    chunks: list[ChunkDraft] = []
    global_chunk_index = 1

    ordered_sources = sorted(
        sources,
        key=lambda source: (
            source.unit_index,
            source.unit_id,
        ),
    )

    for source in ordered_sources:
        text = source.content.strip()

        if not text:
            continue

        target_tokens = (
            _adaptive_target_tokens(
                source=source,
                config=active_config,
            )
        )

        spans = _prepare_spans(
            text=text,
            max_tokens=(
                active_config
                .max_chunk_tokens
            ),
        )

        windows = _build_windows(
            spans=spans,
            target_tokens=target_tokens,
            min_tokens=(
                active_config
                .min_chunk_tokens
            ),
            max_tokens=(
                active_config
                .max_chunk_tokens
            ),
            overlap_tokens=(
                active_config
                .overlap_tokens
            ),
        )

        if not windows:
            continue

        section_path = _section_path(
            source
        )

        start_page, end_page = (
            _page_range(source)
        )

        parent_chunk_id: str | None = None

        if len(windows) > 1:
            parent_chunk_id = (
                _stable_chunk_id(
                    source=source,
                    strategy_version=(
                        active_config
                        .strategy_version
                    ),
                    role="summary",
                    local_index=0,
                )
            )

            summary_content = (
                _extract_parent_summary(
                    content=text,
                    token_limit=(
                        active_config
                        .parent_summary_tokens
                    ),
                )
            )

            chunks.append(
                ChunkDraft(
                    id=parent_chunk_id,
                    document_id=(
                        source.document_id
                    ),
                    document_unit_id=(
                        source.unit_id
                    ),
                    parent_chunk_id=None,
                    chunk_index=(
                        global_chunk_index
                    ),
                    chunk_level=1,
                    chunk_role="summary",
                    source_label=(
                        source.source_label
                    ),
                    section_path=(
                        section_path
                    ),
                    content=summary_content,
                    embedding_content=(
                        _embedding_content(
                            source=source,
                            section_path=(
                                section_path
                            ),
                            content=(
                                summary_content
                            ),
                            role="summary",
                        )
                    ),
                    content_hash=(
                        _hash_content(
                            summary_content
                        )
                    ),
                    token_count=(
                        estimate_tokens(
                            summary_content
                        )
                    ),
                    char_count=len(
                        summary_content
                    ),
                    word_count=(
                        _count_words(
                            summary_content
                        )
                    ),
                    start_char=0,
                    end_char=len(text),
                    start_page=start_page,
                    end_page=end_page,
                    strategy_version=(
                        active_config
                        .strategy_version
                    ),
                    metadata={
                        "summary_method": (
                            "extractive-prefix"
                        ),
                        "child_count": len(
                            windows
                        ),
                        "unit_index": (
                            source.unit_index
                        ),
                        "unit_type": (
                            source.unit_type
                        ),
                        "citation_label": (
                            source.source_label
                        ),
                    },
                )
            )

            global_chunk_index += 1

        for window_index, (
            span_start_index,
            span_end_index,
        ) in enumerate(
            windows,
            start=1,
        ):
            first_span = spans[
                span_start_index
            ]

            last_span = spans[
                span_end_index - 1
            ]

            start_char = first_span.start
            end_char = last_span.end

            chunk_content = text[
                start_char:end_char
            ].strip()

            chunk_id = _stable_chunk_id(
                source=source,
                strategy_version=(
                    active_config
                    .strategy_version
                ),
                role="content",
                local_index=window_index,
            )

            chunks.append(
                ChunkDraft(
                    id=chunk_id,
                    document_id=(
                        source.document_id
                    ),
                    document_unit_id=(
                        source.unit_id
                    ),
                    parent_chunk_id=(
                        parent_chunk_id
                    ),
                    chunk_index=(
                        global_chunk_index
                    ),
                    chunk_level=0,
                    chunk_role="content",
                    source_label=(
                        source.source_label
                    ),
                    section_path=(
                        section_path
                    ),
                    content=chunk_content,
                    embedding_content=(
                        _embedding_content(
                            source=source,
                            section_path=(
                                section_path
                            ),
                            content=(
                                chunk_content
                            ),
                            role="content",
                        )
                    ),
                    content_hash=(
                        _hash_content(
                            chunk_content
                        )
                    ),
                    token_count=(
                        estimate_tokens(
                            chunk_content
                        )
                    ),
                    char_count=len(
                        chunk_content
                    ),
                    word_count=(
                        _count_words(
                            chunk_content
                        )
                    ),
                    start_char=start_char,
                    end_char=end_char,
                    start_page=start_page,
                    end_page=end_page,
                    strategy_version=(
                        active_config
                        .strategy_version
                    ),
                    metadata={
                        "window_index": (
                            window_index
                        ),
                        "window_count": len(
                            windows
                        ),
                        "target_tokens": (
                            target_tokens
                        ),
                        "overlap_tokens": (
                            active_config
                            .overlap_tokens
                        ),
                        "unit_index": (
                            source.unit_index
                        ),
                        "unit_type": (
                            source.unit_type
                        ),
                        "citation_label": (
                            source.source_label
                        ),
                    },
                )
            )

            global_chunk_index += 1

    return chunks
