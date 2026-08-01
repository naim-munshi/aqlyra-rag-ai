import csv
import io
import re
from pathlib import Path

from app.parsers.common import (
    calculate_quality_score,
    create_parsed_unit,
    normalize_text,
)
from app.parsers.types import (
    DocumentParsingError,
    ParseResult,
    ParsedUnit,
)


MAX_CSV_ROWS = 50_000
MAX_CSV_COLUMNS = 200


def _read_utf8_file(path: Path) -> str:
    try:
        return path.read_text(
            encoding="utf-8-sig"
        )
    except UnicodeDecodeError as exc:
        raise DocumentParsingError(
            "Text documents must use UTF-8 encoding"
        ) from exc
    except OSError as exc:
        raise DocumentParsingError(
            "The text document could not be read"
        ) from exc


def _parse_markdown_sections(
    text: str,
) -> list[ParsedUnit]:
    heading_pattern = re.compile(
        r"^(#{1,6})[ \t]+(.+?)[ \t]*$",
        flags=re.MULTILINE,
    )

    matches = list(
        heading_pattern.finditer(text)
    )

    if not matches:
        return [
            create_parsed_unit(
                unit_index=1,
                unit_type="section",
                source_label="Document",
                content=text,
                metadata={
                    "heading": None,
                    "heading_level": None,
                },
            )
        ]

    units: list[ParsedUnit] = []

    preface = normalize_text(
        text[:matches[0].start()]
    )

    if preface:
        units.append(
            create_parsed_unit(
                unit_index=1,
                unit_type="section",
                source_label="Introduction",
                content=preface,
                metadata={
                    "heading": None,
                    "heading_level": None,
                },
            )
        )

    for match_index, match in enumerate(matches):
        content_start = match.end()

        content_end = (
            matches[match_index + 1].start()
            if match_index + 1 < len(matches)
            else len(text)
        )

        heading = normalize_text(
            match.group(2)
        )
        heading_level = len(match.group(1))
        body = normalize_text(
            text[content_start:content_end]
        )

        complete_content = (
            f"{heading}\n\n{body}"
            if body
            else heading
        )

        units.append(
            create_parsed_unit(
                unit_index=len(units) + 1,
                unit_type="section",
                source_label=heading,
                content=complete_content,
                metadata={
                    "heading": heading,
                    "heading_level": heading_level,
                },
            )
        )

    return units


class PlainTextParser:
    extensions = frozenset({".txt", ".md"})

    def parse(self, path: Path) -> ParseResult:
        text = _read_utf8_file(path)
        extension = path.suffix.lower()

        if extension == ".md":
            units = _parse_markdown_sections(
                text
            )
        else:
            units = [
                create_parsed_unit(
                    unit_index=1,
                    unit_type="text",
                    source_label="Text",
                    content=text,
                    metadata={
                        "encoding": "utf-8",
                    },
                )
            ]

        return ParseResult(
            parser_name="builtin-text",
            file_extension=extension,
            units=tuple(units),
            page_count=None,
            word_count=sum(
                unit.word_count for unit in units
            ),
            quality_score=calculate_quality_score(
                units
            ),
            requires_ocr=False,
        )


class CSVParser:
    extensions = frozenset({".csv"})

    def parse(self, path: Path) -> ParseResult:
        text = _read_utf8_file(path)

        sample = text[:8192]

        try:
            dialect = csv.Sniffer().sniff(
                sample,
                delimiters=",;\t|",
            )
        except csv.Error:
            dialect = csv.excel

        reader = csv.reader(
            io.StringIO(text),
            dialect,
        )

        rows: list[list[str]] = []
        truncated = False

        for row_number, row in enumerate(
            reader,
            start=1,
        ):
            if row_number > MAX_CSV_ROWS:
                truncated = True
                break

            if len(row) > MAX_CSV_COLUMNS:
                row = row[:MAX_CSV_COLUMNS]
                truncated = True

            cleaned_row = [
                normalize_text(cell).replace(
                    "\n",
                    " / ",
                )
                for cell in row
            ]

            while cleaned_row and not cleaned_row[-1]:
                cleaned_row.pop()

            if any(cleaned_row):
                rows.append(cleaned_row)

        content = "\n".join(
            "\t".join(row)
            for row in rows
        )

        units = [
            create_parsed_unit(
                unit_index=1,
                unit_type="sheet",
                source_label="CSV",
                content=content,
                metadata={
                    "delimiter": dialect.delimiter,
                    "extracted_rows": len(rows),
                    "truncated": truncated,
                },
            )
        ]

        return ParseResult(
            parser_name="builtin-csv",
            file_extension=".csv",
            units=tuple(units),
            page_count=None,
            word_count=sum(
                unit.word_count for unit in units
            ),
            quality_score=calculate_quality_score(
                units
            ),
            requires_ocr=False,
        )