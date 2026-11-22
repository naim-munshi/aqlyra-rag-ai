"""Synthetic PDF and failure logging regressions; no private input."""
from pathlib import Path

import pytest
from pypdf import PdfWriter

from app.config.settings import settings
from app.parsers import pdf_parser
from app.parsers.pdf_parser import PDFParser
from app.parsers.types import DocumentParsingError
from app.services.knowledge_index_queue import safe_index_failure_reason


def test_zero_page_pdf_is_rejected(tmp_path):
    file = tmp_path / "zero-pages.pdf"
    with file.open("wb") as handle:
        PdfWriter().write(handle)
    with pytest.raises(DocumentParsingError, match="no pages"):
        PDFParser().parse(file)


def test_unreadable_page_tree_is_sanitized(monkeypatch):
    class BadPages:
        def __len__(self):
            raise ValueError("SENSITIVE-PARSER-OUTPUT")

    class Reader:
        is_encrypted = False
        pages = BadPages()

    monkeypatch.setattr(pdf_parser, "PdfReader", lambda _: Reader())
    with pytest.raises(DocumentParsingError, match="page structure") as caught:
        PDFParser().parse(Path("synthetic.pdf"))
    assert "SENSITIVE-PARSER-OUTPUT" not in str(caught.value)


def test_page_extraction_exceptions_do_not_persist_private_error_details(monkeypatch):
    class Page:
        def __init__(self, should_fail):
            self.should_fail = should_fail
            self.mediabox = type("Box", (), {"width": 300, "height": 400})()

        def extract_text(self, **kwargs):
            if self.should_fail:
                raise RuntimeError("SENSITIVE-DOC-PRIVATE-TEXT")
            return "Public synthetic paragraph with plenty of searchable words."

    class Reader:
        is_encrypted = False
        pages = [Page(False), Page(True)]

    monkeypatch.setattr(pdf_parser, "PdfReader", lambda _: Reader())
    monkeypatch.setattr(settings, "KNOWLEDGE_PDF_OCR_ENABLED", False)
    result = PDFParser().parse(Path("synthetic.pdf"))
    assert result.units[1].metadata["extraction_error"] == "RuntimeError"
    assert "SENSITIVE-DOC-PRIVATE-TEXT" not in str(result.units[1].metadata)


@pytest.mark.parametrize("message,expected", [
    ("PDF contains no searchable text; scanned pages require OCR", "pdf_no_searchable_text"),
    ("Scanned PDF exceeds the supported OCR page limit", "pdf_ocr_page_limit"),
    ("PDF OCR page timed out", "pdf_ocr_timeout"),
    ("PDF OCR components unavailable", "pdf_ocr_unavailable"),
    ("The PDF file could not be read", "pdf_invalid_structure"),
    ("SENSITIVE-UNKNOWN-DATA", "document_parse_error_other"),
])
def test_only_safe_pdf_reasons_are_exposed(message, expected):
    code = safe_index_failure_reason(DocumentParsingError(message))
    assert code == expected
    assert "SENSITIVE" not in code


def test_non_pdf_provider_exception_is_only_classified_by_type():
    assert safe_index_failure_reason(RuntimeError("TOP-SECRET")) == "RuntimeError"
