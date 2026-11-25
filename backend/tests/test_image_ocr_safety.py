"""Bound image OCR before any high-memory raster operation.

Synthetic mock only: no user image bytes, provider API or production DB.
"""
from pathlib import Path
from unittest.mock import Mock

import pytest

from app.parsers.image_parser import ImageOCRParser, MAX_OCR_IMAGE_PIXELS
from app.parsers.types import DocumentParsingError
from app.parsers import image_parser


@pytest.mark.parametrize("size", [(9001, 1000), (10000, 10000), (0, 20)])
def test_large_or_invalid_image_refused_before_decode(monkeypatch, size):
    source = Mock()
    source.__enter__ = Mock(return_value=source)
    source.__exit__ = Mock(return_value=False)
    source.format = "PNG"
    source.size = size
    monkeypatch.setattr(image_parser.Image, "open", lambda _: source)
    monkeypatch.setattr(
        image_parser.ImageOps, "exif_transpose",
        lambda _: pytest.fail("Oversized image was decoded"),
    )
    monkeypatch.setattr(
        image_parser.pytesseract, "image_to_string",
        lambda *a, **k: pytest.fail("Oversized image was OCR processed"),
    )
    with pytest.raises(DocumentParsingError, match="pixel limit"):
        ImageOCRParser().parse(Path("synthetic.png"))


def test_ocr_pixel_budget_matches_pdf_raster_budget():
    assert MAX_OCR_IMAGE_PIXELS == 9_000_000
