"""Adversarial PDF safety budgets: bounded parsing and private diagnostics."""
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.parsers import pdf_parser
from app.parsers.types import DocumentParsingError


class FakePage:
    mediabox = SimpleNamespace(width=612, height=792)

    def __init__(self, content: str = "", *, error: bool = False):
        self.content = content
        self.error = error
        self.calls = 0

    def extract_text(self, **_kwargs):
        self.calls += 1
        if self.error:
            raise ValueError("private-file-path-or-secret-must-not-leak")
        return self.content


def reader(monkeypatch, pages):
    stub = SimpleNamespace(is_encrypted=False, pages=pages)
    monkeypatch.setattr(pdf_parser, "PdfReader", lambda _path: stub)
    return pdf_parser.PDFParser()


def test_pdf_rejects_excessive_pages_before_any_extraction(monkeypatch):
    pages = [FakePage("hello"), FakePage("world")]
    parser = reader(monkeypatch, pages)
    monkeypatch.setattr(pdf_parser, "MAX_PDF_PAGES", 1)
    with pytest.raises(DocumentParsingError, match="page safety limit"):
        parser.parse(Path("fake.pdf"))
    assert all(page.calls == 0 for page in pages)


def test_pdf_rejects_single_page_expanding_to_excessive_text(monkeypatch):
    parser = reader(monkeypatch, [FakePage("x" * 21)])
    monkeypatch.setattr(pdf_parser, "MAX_PDF_PAGE_CHARACTERS", 20)
    with pytest.raises(DocumentParsingError, match="page exceeds the text safety"):
        parser.parse(Path("fake.pdf"))


def test_pdf_rejects_total_extracted_text_over_budget(monkeypatch):
    parser = reader(monkeypatch, [FakePage("a" * 9), FakePage("b" * 9)])
    monkeypatch.setattr(pdf_parser, "MAX_PDF_TOTAL_CHARACTERS", 15)
    with pytest.raises(DocumentParsingError, match="PDF exceeds the text safety"):
        parser.parse(Path("fake.pdf"))


def test_pdf_parser_error_metadata_does_not_expose_exception_details(monkeypatch):
    parser = reader(monkeypatch, [FakePage(error=True)])
    result = parser.parse(Path("fake.pdf"))
    assert result.units[0].metadata["extraction_error"] == "ValueError"
    assert "private-file-path-or-secret" not in str(result)


def test_normal_small_pdf_remains_supported(monkeypatch):
    parser = reader(monkeypatch, [FakePage("Aqlyra private RAG document")])
    result = parser.parse(Path("fake.pdf"))
    assert result.page_count == 1
    assert len(result.units) == 1
    assert "Aqlyra" in result.units[0].content
