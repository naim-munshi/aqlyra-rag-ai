from pathlib import Path
from typing import Any

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.parsers.common import (
    calculate_quality_score,
    create_parsed_unit,
)
from app.parsers.types import (
    DocumentParsingError,
    EncryptedDocumentError,
    ParseResult,
    ParsedUnit,
)


# A small PDF can advertise huge page counts or expand into vast text.
# Bound parser work before generating units/embeddings for attacker-supplied files.
MAX_PDF_PAGES = 500
MAX_PDF_PAGE_CHARACTERS = 200_000
MAX_PDF_TOTAL_CHARACTERS = 2_000_000


class PDFParser:
    extensions = frozenset({".pdf"})

    def parse(self, path: Path) -> ParseResult:
        try:
            reader = PdfReader(str(path))

            if reader.is_encrypted:
                unlocked = reader.decrypt("")

                if not unlocked:
                    raise EncryptedDocumentError(
                        "Password-protected PDFs are not supported"
                    )

        except EncryptedDocumentError:
            raise

        except PdfReadError as exc:
            raise DocumentParsingError(
                "The PDF file could not be read"
            ) from exc

        except OSError as exc:
            raise DocumentParsingError(
                "The PDF file could not be opened"
            ) from exc

        units: list[ParsedUnit] = []
        try:
            total_pages = len(reader.pages)
        except Exception as exc:
            raise DocumentParsingError("The PDF page structure is invalid") from exc
        if total_pages > MAX_PDF_PAGES:
            raise DocumentParsingError("The PDF exceeds the page safety limit")
        extracted_characters = 0

        for page_number, page in enumerate(
            reader.pages,
            start=1,
        ):
            extraction_error: str | None = None

            try:
                content = (
                    page.extract_text(
                        extraction_mode="layout"
                    )
                    or ""
                )

            except Exception:
                try:
                    content = page.extract_text() or ""

                except Exception as exc:
                    content = ""
                    # Do not store parser exception messages containing
                    # paths, document fragments, or processing internals.
                    extraction_error = type(exc).__name__

            if len(content) > MAX_PDF_PAGE_CHARACTERS:
                raise DocumentParsingError("A PDF page exceeds the text safety limit")
            extracted_characters += len(content)
            if extracted_characters > MAX_PDF_TOTAL_CHARACTERS:
                raise DocumentParsingError("The PDF exceeds the text safety limit")

            metadata: dict[str, Any] = {
                "page_number": page_number,
            }

            try:
                metadata["width"] = float(
                    page.mediabox.width
                )
                metadata["height"] = float(
                    page.mediabox.height
                )
            except (TypeError, ValueError):
                pass

            if extraction_error is not None:
                metadata["extraction_error"] = extraction_error

            units.append(
                create_parsed_unit(
                    unit_index=page_number,
                    unit_type="page",
                    source_label=f"Page {page_number}",
                    content=content,
                    metadata=metadata,
                )
            )

        text_page_count = sum(
            1 for unit in units if unit.char_count >= 20
        )

        total_characters = sum(
            unit.char_count for unit in units
        )

        text_coverage = (
            text_page_count / total_pages
            if total_pages
            else 0.0
        )

        requires_ocr = bool(
            total_pages
            and (
                text_coverage < 0.5
                or total_characters < total_pages * 40
            )
        )

        return ParseResult(
            parser_name="pypdf",
            file_extension=".pdf",
            units=tuple(units),
            page_count=total_pages,
            word_count=sum(
                unit.word_count for unit in units
            ),
            quality_score=calculate_quality_score(
                units,
                expected_unit_count=total_pages,
            ),
            requires_ocr=requires_ocr,
        )