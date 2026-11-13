"""Bounded multilingual OCR for a single PDF page, never the entire file.

The caller only gives an already-verified local temporary PDF. Poppler
renders ONE selected page at a capped resolution; Tesseract runs with its
own timeout. No remote provider, document mutation, or retained images.
"""
from pathlib import Path
from tempfile import TemporaryDirectory
import subprocess

import pytesseract
from PIL import Image, ImageOps, UnidentifiedImageError
from pytesseract import TesseractError, TesseractNotFoundError

from app.parsers.common import normalize_text
from app.parsers.types import DocumentParsingError

OCR_LANGUAGES = "eng+jpn+ben"
_MAX_RASTER_BYTES = 20 * 1024 * 1024
_MAX_RASTER_PIXELS = 9_000_000


def ocr_pdf_page(
    *, pdf_path: Path, page_number: int, timeout_seconds: int = 15,
) -> str:
    if page_number < 1 or not 5 <= timeout_seconds <= 45:
        raise ValueError("Invalid OCR limits")
    with TemporaryDirectory(prefix="aqlyra-pdf-ocr-") as output_dir:
        prefix = Path(output_dir) / "page"
        command = [
            "pdftoppm",
            "-f", str(page_number), "-l", str(page_number),
            "-singlefile", "-scale-to", "2200",
            "-png", str(pdf_path), str(prefix),
        ]
        try:
            subprocess.run(
                command, check=True, capture_output=True,
                timeout=timeout_seconds,
            )
            image_path = prefix.with_suffix(".png")
            if not image_path.is_file() or (
                image_path.stat().st_size > _MAX_RASTER_BYTES
            ):
                raise DocumentParsingError("PDF page raster exceeds OCR limit")
            with Image.open(image_path) as source:
                if source.width * source.height > _MAX_RASTER_PIXELS:
                    raise DocumentParsingError("PDF image dimensions exceed OCR limit")
                prepared = ImageOps.autocontrast(source.convert("L"))
                content = pytesseract.image_to_string(
                    prepared, lang=OCR_LANGUAGES, timeout=timeout_seconds,
                )
                return normalize_text(content)
        except (subprocess.TimeoutExpired, RuntimeError) as exc:
            raise DocumentParsingError("PDF OCR page timed out") from exc
        except (FileNotFoundError, TesseractNotFoundError) as exc:
            raise DocumentParsingError("PDF OCR components unavailable") from exc
        except (subprocess.CalledProcessError, TesseractError) as exc:
            raise DocumentParsingError("PDF OCR could not process page") from exc
        except (OSError, UnidentifiedImageError, ValueError) as exc:
            raise DocumentParsingError("PDF OCR raster invalid") from exc
