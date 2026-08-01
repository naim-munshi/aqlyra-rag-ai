from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Protocol


UnitType = Literal[
    "page",
    "slide",
    "sheet",
    "section",
    "text",
]


class DocumentParsingError(Exception):
    """Base exception for document parsing failures."""


class UnsupportedDocumentError(DocumentParsingError):
    """Raised when no parser exists for a file extension."""


class EncryptedDocumentError(DocumentParsingError):
    """Raised when an encrypted document cannot be opened."""


@dataclass(frozen=True, slots=True)
class ParsedUnit:
    unit_index: int
    unit_type: UnitType
    source_label: str
    content: str
    content_hash: str
    char_count: int
    word_count: int
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ParseResult:
    parser_name: str
    file_extension: str
    units: tuple[ParsedUnit, ...]
    page_count: int | None
    word_count: int
    quality_score: float
    requires_ocr: bool

    @property
    def unit_count(self) -> int:
        return len(self.units)


class DocumentParser(Protocol):
    extensions: frozenset[str]

    def parse(self, path: Path) -> ParseResult:
        """Parse a document into structured source units."""