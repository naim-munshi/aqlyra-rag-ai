from pathlib import Path

import pytesseract
from PIL import Image, ImageOps
from pytesseract import (
    TesseractError,
    TesseractNotFoundError,
)

from app.parsers.common import (
    calculate_quality_score,
    create_parsed_unit,
    normalize_text,
)
from app.parsers.types import (
    DocumentParsingError,
    ParseResult,
)


OCR_LANGUAGES = "eng+jpn+ben"
OCR_TIMEOUT_SECONDS = 30


class ImageOCRParser:
    extensions = frozenset(
        {
            ".png",
            ".jpg",
            ".jpeg",
            ".webp",
        }
    )

    def parse(
        self,
        path: Path,
    ) -> ParseResult:
        try:
            with Image.open(path) as source_image:
                image_format = (
                    source_image.format
                    or "UNKNOWN"
                )

                oriented_image = (
                    ImageOps.exif_transpose(
                        source_image
                    )
                )

                width, height = oriented_image.size

                prepared_image = (
                    ImageOps.autocontrast(
                        oriented_image.convert("L")
                    )
                )

                extracted_text = (
                    pytesseract.image_to_string(
                        prepared_image,
                        lang=OCR_LANGUAGES,
                        timeout=OCR_TIMEOUT_SECONDS,
                    )
                )

        except TesseractNotFoundError as exc:
            raise DocumentParsingError(
                "Tesseract OCR is not installed "
                "or cannot be found"
            ) from exc

        except TesseractError as exc:
            raise DocumentParsingError(
                "Tesseract could not process "
                "the image"
            ) from exc

        except RuntimeError as exc:
            raise DocumentParsingError(
                "Image OCR timed out"
            ) from exc

        except OSError as exc:
            raise DocumentParsingError(
                "The image could not be opened"
            ) from exc

        normalized_text = normalize_text(
            extracted_text
        )

        if not normalized_text:
            raise DocumentParsingError(
                "OCR could not extract readable "
                "text from the image"
            )

        unit = create_parsed_unit(
            unit_index=1,
            unit_type="text",
            source_label="Image OCR",
            content=normalized_text,
            metadata={
                "source_type": "image_ocr",
                "image_format": image_format,
                "width": width,
                "height": height,
                "ocr_languages": OCR_LANGUAGES,
            },
        )

        units = [unit]

        return ParseResult(
            parser_name="image_ocr",
            file_extension=path.suffix.lower(),
            units=tuple(units),
            page_count=1,
            word_count=unit.word_count,
            quality_score=(
                calculate_quality_score(
                    units,
                    expected_unit_count=1,
                )
            ),
            requires_ocr=True,
        )