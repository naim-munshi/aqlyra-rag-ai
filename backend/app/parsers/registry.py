from pathlib import Path

from app.parsers.image_parser import ImageOCRParser
from app.parsers.office_parser import (
    DOCXParser,
    PPTXParser,
    XLSXParser,
)
from app.parsers.pdf_parser import PDFParser
from app.parsers.text_parser import (
    CSVParser,
    PlainTextParser,
)
from app.parsers.types import (
    DocumentParser,
    ParseResult,
    UnsupportedDocumentError,
)


_PARSERS: tuple[DocumentParser, ...] = (
    PDFParser(),
    DOCXParser(),
    PPTXParser(),
    XLSXParser(),
    ImageOCRParser(),
    PlainTextParser(),
    CSVParser(),
)


_PARSER_BY_EXTENSION: dict[str, DocumentParser] = {
    extension: parser
    for parser in _PARSERS
    for extension in parser.extensions
}


def parse_document(
    path: str | Path,
    file_extension: str | None = None,
) -> ParseResult:
    document_path = Path(path).expanduser().resolve()

    if not document_path.exists():
        raise FileNotFoundError(
            f"Document not found: {document_path}"
        )

    if not document_path.is_file():
        raise ValueError(
            f"Document path is not a file: {document_path}"
        )

    extension = (
        file_extension or document_path.suffix
    ).lower()

    if not extension.startswith("."):
        extension = f".{extension}"

    parser = _PARSER_BY_EXTENSION.get(
        extension
    )

    if parser is None:
        raise UnsupportedDocumentError(
            f"No parser is available for {extension}"
        )

    return parser.parse(document_path)