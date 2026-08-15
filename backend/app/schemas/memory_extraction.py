import re
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)


MemoryExtractionKind = Literal[
    "fact",
    "preference",
    "goal",
    "decision",
]


_CITATION_PATTERN = re.compile(
    r"\[S\d+\]",
    flags=re.IGNORECASE,
)

_SECRET_PATTERNS = (
    re.compile(
        r"\b(?:api[_ -]?key|access[_ -]?token|"
        r"auth(?:entication)?[_ -]?token|password|"
        r"passwd|pwd|secret)\b"
        r"\s*(?:is|=|:)\s*\S+",
        flags=re.IGNORECASE,
    ),
    re.compile(
        r"\bBearer\s+[A-Za-z0-9._~+/=-]{12,}",
        flags=re.IGNORECASE,
    ),
    re.compile(
        r"\bsk-[A-Za-z0-9_-]{16,}\b",
        flags=re.IGNORECASE,
    ),
    re.compile(
        r"\bgh[pousr]_[A-Za-z0-9]{20,}\b",
        flags=re.IGNORECASE,
    ),
    re.compile(
        r"\bAKIA[0-9A-Z]{16}\b",
    ),
)

_CARD_PATTERN = re.compile(
    r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)"
)


def _passes_luhn(value: str) -> bool:
    total = 0
    parity = len(value) % 2

    for index, character in enumerate(value):
        digit = int(character)

        if index % 2 == parity:
            digit *= 2

            if digit > 9:
                digit -= 9

        total += digit

    return total % 10 == 0


def _contains_payment_card(
    value: str,
) -> bool:
    for match in _CARD_PATTERN.finditer(value):
        digits = re.sub(
            r"\D",
            "",
            match.group(0),
        )

        if (
            13 <= len(digits) <= 19
            and _passes_luhn(digits)
        ):
            return True

    return False


def _contains_sensitive_secret(
    value: str,
) -> bool:
    if any(
        pattern.search(value)
        for pattern in _SECRET_PATTERNS
    ):
        return True

    return _contains_payment_card(value)


class MemoryCandidate(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )

    kind: MemoryExtractionKind

    content: str = Field(
        min_length=1,
        max_length=500,
    )

    importance: float = Field(
        ge=0.0,
        le=1.0,
    )

    confidence: float = Field(
        ge=0.0,
        le=1.0,
    )

    @field_validator("content")
    @classmethod
    def normalize_content(
        cls,
        value: str,
    ) -> str:
        cleaned = " ".join(
            value.split()
        )

        if not cleaned:
            raise ValueError(
                "Memory content cannot be empty"
            )

        if _CITATION_PATTERN.search(
            cleaned
        ):
            raise ValueError(
                "Personal memory cannot contain "
                "document citation markers"
            )

        if _contains_sensitive_secret(
            cleaned
        ):
            raise ValueError(
                "Sensitive credentials or payment "
                "data cannot be stored as memory"
            )

        return cleaned


class MemoryExtractionResponse(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )

    memories: list[MemoryCandidate] = Field(
        default_factory=list,
        max_length=8,
    )
