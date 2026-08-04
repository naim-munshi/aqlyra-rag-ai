import re
from collections.abc import Sequence

from app.rag.answer_types import (
    GroundedAnswerDraft,
    INSUFFICIENT_EVIDENCE_SENTINEL,
)
from app.rag.citation_types import (
    CitationValidationError,
    MalformedCitationError,
    MissingCitationError,
    UncitedClaimError,
    UnknownCitationError,
    ValidatedGroundedAnswer,
)


_VALID_CITATION_PATTERN = re.compile(
    r"\[(S[1-9][0-9]*)\]"
)

_SOURCE_LIKE_PATTERN = re.compile(
    r"\[([Ss][0-9]+)\]"
)

_HEADING_PATTERN = re.compile(
    r"^\s*#{1,6}\s+"
)

_BULLET_PATTERN = re.compile(
    r"^\s*(?:[-*+]|\d+[.)])\s+"
)

_CONTENT_TOKEN_PATTERN = re.compile(
    r"[A-Za-z0-9]+(?:['’-][A-Za-z0-9]+)*"
    r"|[\u3040-\u30ff]"
    r"|[\u3400-\u9fff]"
    r"|[\uac00-\ud7af]",
    flags=re.UNICODE,
)


def _ordered_unique(
    values: Sequence[str],
) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []

    for value in values:
        if value in seen:
            continue

        seen.add(value)
        ordered.append(value)

    return tuple(ordered)


def _extract_claim_blocks(
    answer_text: str,
) -> tuple[str, ...]:
    blocks: list[str] = []
    paragraph_lines: list[str] = []

    def flush_paragraph() -> None:
        if not paragraph_lines:
            return

        paragraph = " ".join(
            paragraph_lines
        ).strip()

        if paragraph:
            blocks.append(paragraph)

        paragraph_lines.clear()

    for raw_line in answer_text.splitlines():
        line = raw_line.strip()

        if not line:
            flush_paragraph()
            continue

        if _HEADING_PATTERN.match(line):
            flush_paragraph()
            blocks.append(line)
            continue

        if _BULLET_PATTERN.match(line):
            flush_paragraph()
            blocks.append(line)
            continue

        paragraph_lines.append(line)

    flush_paragraph()

    return tuple(blocks)


def _requires_citation(
    block: str,
) -> bool:
    if _HEADING_PATTERN.match(block):
        return False

    without_citations = (
        _VALID_CITATION_PATTERN.sub(
            "",
            block,
        )
    )

    plain_text = re.sub(
        r"[*_`>#]",
        "",
        without_citations,
    ).strip()

    tokens = _CONTENT_TOKEN_PATTERN.findall(
        plain_text
    )

    if not tokens:
        return False

    if (
        plain_text.endswith(":")
        and len(tokens) <= 8
    ):
        return False

    return True


def _preview_block(
    block: str,
    limit: int = 120,
) -> str:
    normalized = re.sub(
        r"\s+",
        " ",
        block,
    ).strip()

    if len(normalized) <= limit:
        return normalized

    return (
        normalized[: limit - 1].rstrip()
        + "…"
    )


def validate_grounded_answer_draft(
    draft: GroundedAnswerDraft,
) -> ValidatedGroundedAnswer:
    answer_text = draft.answer_text.strip()

    if not answer_text:
        raise CitationValidationError(
            "Grounded answer cannot be empty"
        )

    sentinel_present = (
        INSUFFICIENT_EVIDENCE_SENTINEL
        in answer_text
    )

    if (
        sentinel_present
        and answer_text
        != INSUFFICIENT_EVIDENCE_SENTINEL
    ):
        raise CitationValidationError(
            "The insufficient-evidence sentinel "
            "must be returned without additional text"
        )

    if (
        answer_text
        == INSUFFICIENT_EVIDENCE_SENTINEL
    ):
        return ValidatedGroundedAnswer(
            draft=draft,
            citation_ids=(),
            cited_sources=(),
            citation_count=0,
            is_refusal=True,
        )

    source_ids = [
        source.source_id
        for source in draft.sources
    ]

    if len(source_ids) != len(
        set(source_ids)
    ):
        raise CitationValidationError(
            "Grounded answer sources contain "
            "duplicate source IDs"
        )

    source_map = {
        source.source_id: source
        for source in draft.sources
    }

    malformed_citations: list[str] = []

    for match in _SOURCE_LIKE_PATTERN.finditer(
        answer_text
    ):
        citation_value = match.group(1)

        if re.fullmatch(
            r"S[1-9][0-9]*",
            citation_value,
        ) is None:
            malformed_citations.append(
                match.group(0)
            )

    if malformed_citations:
        malformed_text = ", ".join(
            _ordered_unique(
                malformed_citations
            )
        )

        raise MalformedCitationError(
            "Malformed citation reference: "
            f"{malformed_text}"
        )

    citation_matches = list(
        _VALID_CITATION_PATTERN.finditer(
            answer_text
        )
    )

    if not citation_matches:
        raise MissingCitationError(
            "Grounded answer must contain "
            "at least one source citation"
        )

    all_citation_ids = tuple(
        match.group(1)
        for match in citation_matches
    )

    citation_ids = _ordered_unique(
        all_citation_ids
    )

    unknown_ids = tuple(
        source_id
        for source_id in citation_ids
        if source_id not in source_map
    )

    if unknown_ids:
        formatted_unknown = ", ".join(
            f"[{source_id}]"
            for source_id in unknown_ids
        )

        raise UnknownCitationError(
            "Answer references unknown sources: "
            f"{formatted_unknown}"
        )

    uncited_blocks: list[str] = []

    for block in _extract_claim_blocks(
        answer_text
    ):
        if not _requires_citation(block):
            continue

        if (
            _VALID_CITATION_PATTERN.search(
                block
            )
            is None
        ):
            uncited_blocks.append(block)

    if uncited_blocks:
        preview = _preview_block(
            uncited_blocks[0]
        )

        raise UncitedClaimError(
            "Answer contains an uncited "
            f"evidence block: {preview}"
        )

    cited_sources = tuple(
        source_map[source_id]
        for source_id in citation_ids
    )

    return ValidatedGroundedAnswer(
        draft=draft,
        citation_ids=citation_ids,
        cited_sources=cited_sources,
        citation_count=len(
            all_citation_ids
        ),
        is_refusal=False,
    )
