import hashlib
import re
import unicodedata
from typing import Any

from app.parsers.types import ParsedUnit, UnitType


_MULTILINGUAL_WORD_PATTERN = re.compile(
    r"[A-Za-z0-9]+(?:['’-][A-Za-z0-9]+)*"
    r"|[\u3040-\u30ff]"
    r"|[\u3400-\u9fff]"
    r"|[\uac00-\ud7af]",
    flags=re.UNICODE,
)


def normalize_text(value: str | None) -> str:
    if not value:
        return ""

    normalized = unicodedata.normalize("NFC", value)
    normalized = normalized.replace("\r\n", "\n")
    normalized = normalized.replace("\r", "\n")
    normalized = normalized.replace("\x00", "")

    lines: list[str] = []

    for line in normalized.split("\n"):
        cleaned_line = re.sub(r"[ \t]+", " ", line).strip()
        lines.append(cleaned_line)

    cleaned = "\n".join(lines)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)

    return cleaned.strip()


def count_words(text: str) -> int:
    return len(_MULTILINGUAL_WORD_PATTERN.findall(text))


def hash_content(text: str) -> str:
    return hashlib.sha256(
        text.encode("utf-8")
    ).hexdigest()


def create_parsed_unit(
    *,
    unit_index: int,
    unit_type: UnitType,
    source_label: str,
    content: str,
    metadata: dict[str, Any] | None = None,
) -> ParsedUnit:
    normalized_content = normalize_text(content)

    return ParsedUnit(
        unit_index=unit_index,
        unit_type=unit_type,
        source_label=source_label[:255],
        content=normalized_content,
        content_hash=hash_content(normalized_content),
        char_count=len(normalized_content),
        word_count=count_words(normalized_content),
        metadata=metadata or {},
    )


def calculate_quality_score(
    units: list[ParsedUnit],
    expected_unit_count: int | None = None,
) -> float:
    expected_count = max(
        expected_unit_count or len(units),
        1,
    )

    non_empty_count = sum(
        1 for unit in units if unit.char_count > 0
    )

    total_characters = sum(
        unit.char_count for unit in units
    )

    coverage_score = min(
        non_empty_count / expected_count,
        1.0,
    )

    density_score = min(
        total_characters / (expected_count * 400),
        1.0,
    )

    final_score = (
        coverage_score * 0.75
        + density_score * 0.25
    )

    return round(
        max(0.0, min(final_score, 1.0)),
        4,
    )