from pathlib import Path
from typing import Any

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.config.settings import settings
from app.parsers.pdf_page_ocr import ocr_pdf_page

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
        total_pages = len(reader.pages)
        ocr_used = 0
        ocr_cap = settings.KNOWLEDGE_PDF_OCR_MAX_PAGES

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
                    extraction_error = (
                        f"{type(exc).__name__}: {str(exc)[:200]}"
                    )

            metadata: dict[str, Any] = {
                "page_number": page_number,
            }
            if len(content.strip()) < 20 and settings.KNOWLEDGE_PDF_OCR_ENABLED:
                if ocr_used >= ocr_cap:
                    raise DocumentParsingError(
                        "Scanned PDF exceeds the supported OCR page limit"
                    )
                content = ocr_pdf_page(
                    pdf_path=path,
                    page_number=page_number,
                    timeout_seconds=settings.KNOWLEDGE_PDF_OCR_PAGE_TIMEOUT_SECONDS,
                )
                ocr_used += 1
                metadata.update({
                    "source_type": "pdf_ocr",
                    "ocr_languages": "eng+jpn+ben",
                })

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
            ocr_used
            or (
                total_pages
                and (
                    text_coverage < 0.5
                    or total_characters < total_pages * 40
                )
            )
        )
        # Never commit a scanned or empty PDF as a searchable "ready" source.
        # Retain the private original and expose a retry after OCR is enabled.
        if total_characters == 0:
            raise DocumentParsingError(
                "PDF contains no searchable text; scanned pages require OCR"
            )

        return ParseResult(
            parser_name="pypdf+ocr" if ocr_used else "pypdf",
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