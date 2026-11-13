"""PDF OCR cannot silently mark unreadable scans as indexed knowledge."""
from pathlib import Path
from unittest.mock import Mock

import pytest
from pypdf import PdfWriter

from app.config.settings import settings
from app.parsers.pdf_parser import PDFParser
from app.parsers.pdf_page_ocr import ocr_pdf_page
from app.parsers.types import DocumentParsingError
from app.parsers import pdf_parser


def _blank_pdf(path: Path, pages: int = 2) -> None:
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=420, height=594)
    with path.open("wb") as out:
        writer.write(out)


def test_scanned_pdf_indexes_real_ocr_pages_and_retains_page_sources(tmp_path, monkeypatch):
    path = tmp_path / "two-scanned-pages.pdf"
    _blank_pdf(path)
    monkeypatch.setattr(settings, "KNOWLEDGE_PDF_OCR_ENABLED", True)
    monkeypatch.setattr(settings, "KNOWLEDGE_PDF_OCR_MAX_PAGES", 4)
    seen = []

    def fake_ocr(*, pdf_path, page_number, timeout_seconds):
        assert pdf_path == path
        seen.append(page_number)
        return f"Private knowledge note {page_number}, unique fact on page {page_number}."

    monkeypatch.setattr(pdf_parser, "ocr_pdf_page", fake_ocr)
    parsed = PDFParser().parse(path)
    assert seen == [1, 2]
    assert parsed.parser_name == "pypdf+ocr"
    assert parsed.page_count == 2
    assert parsed.requires_ocr is True
    assert [unit.source_label for unit in parsed.units] == ["Page 1", "Page 2"]
    assert parsed.units[1].metadata["source_type"] == "pdf_ocr"
    assert parsed.units[1].content.startswith("Private knowledge note 2")


def test_pdf_with_no_text_is_not_falsely_ready_without_ocr(tmp_path, monkeypatch):
    path = tmp_path / "scan.pdf"
    _blank_pdf(path, 1)
    monkeypatch.setattr(settings, "KNOWLEDGE_PDF_OCR_ENABLED", False)
    with pytest.raises(DocumentParsingError, match="require OCR"):
        PDFParser().parse(path)


def test_scanned_pdf_page_cap_fails_closed(tmp_path, monkeypatch):
    path = tmp_path / "too-many.pdf"
    _blank_pdf(path, 3)
    monkeypatch.setattr(settings, "KNOWLEDGE_PDF_OCR_ENABLED", True)
    monkeypatch.setattr(settings, "KNOWLEDGE_PDF_OCR_MAX_PAGES", 2)
    monkeypatch.setattr(pdf_parser, "ocr_pdf_page", lambda **_: "Real extracted page text.")
    with pytest.raises(DocumentParsingError, match="OCR page limit"):
        PDFParser().parse(path)


def test_no_readable_ocr_text_does_not_create_searchable_document(tmp_path, monkeypatch):
    path = tmp_path / "empty.pdf"
    _blank_pdf(path, 1)
    monkeypatch.setattr(settings, "KNOWLEDGE_PDF_OCR_ENABLED", True)
    monkeypatch.setattr(pdf_parser, "ocr_pdf_page", lambda **_: "")
    with pytest.raises(DocumentParsingError, match="no searchable text"):
        PDFParser().parse(path)


def test_ocr_page_invokes_bounded_renderer_and_tesseract(tmp_path, monkeypatch):
    from PIL import Image
    from app.parsers import pdf_page_ocr
    pdf = tmp_path / "source.pdf"
    pdf.write_bytes(b"synthetic mock PDF")
    args_seen = []

    def fake_run(command, **kwargs):
        args_seen.append((command, kwargs))
        Image.new("RGB", (50, 30), "white").save(Path(command[-1]).with_suffix(".png"))
        return Mock(returncode=0)

    monkeypatch.setattr(pdf_page_ocr.subprocess, "run", fake_run)
    monkeypatch.setattr(pdf_page_ocr.pytesseract, "image_to_string",
                        lambda *_args, **kw: "বাংলা এবং 日本語 knowledge page")
    result = ocr_pdf_page(pdf_path=pdf, page_number=2, timeout_seconds=12)
    assert "knowledge page" in result
    assert "-f" in args_seen[0][0] and "2" in args_seen[0][0]
    assert args_seen[0][1]["timeout"] == 12
    assert not list(tmp_path.glob("page*.png"))


def test_ocr_command_cannot_be_swapped_by_user_filename(tmp_path, monkeypatch):
    from app.parsers import pdf_page_ocr
    import subprocess
    pdf = tmp_path / "bad;$(echo bad).pdf"
    pdf.write_bytes(b"safe")
    monkeypatch.setattr(
        pdf_page_ocr.subprocess, "run",
        lambda *a, **kw: (_ for _ in ()).throw(subprocess.TimeoutExpired(a[0], 5)),
    )
    with pytest.raises(DocumentParsingError, match="timed out"):
        ocr_pdf_page(pdf_path=pdf, page_number=1)
