"""Narrow zero-LLM fast lane for a genuinely extracted current-office page.

The parser never hardcodes a person's name, reads user memory, or accepts a
third-party news snippet as current-office evidence. Any uncertain page falls
back to the existing source-grounded LLM path.
"""
from __future__ import annotations

import re

from app.schemas.web_research import WebResearchSource
from app.services.public_office_guard import officeholder_authoritative_url


_US_ADMINISTRATION_HEADING = re.compile(
    r"(?m)^(?:#{1,4}\s*)?President\s+"
    r"([A-Z][A-Za-z.'-]+(?:\s+(?:[A-Z][A-Za-z.'-]+|[A-Z]\.)){1,4})"
    r"\s*$"
)
_BD_PRIME_MINISTER_LABEL = re.compile(
    r"জনাব\s+([\u0980-\u09ff]{2,}(?:\s+[\u0980-\u09ff]{2,}){1,3})"
    r"\s*(?:\n|\|)\s*প্রধানমন্ত্রী(?=\s|$|[।|])"
)


def _clean_official_page(value: str) -> str:
    # Only plain text returned by Tavily's webpage extraction is accepted.
    # Do not parse arbitrary LLM output, snippets or user-supplied HTML.
    return value.replace("\r\n", "\n").replace("\r", "\n")


def verified_officeholder_fast_answer(
    question: str,
    sources: list[WebResearchSource],
    *,
    extracted_urls: set[str],
) -> tuple[str, WebResearchSource] | None:
    """Return a concise evidence-cited answer only from a strict primary page.

    extracted_urls identifies pages obtained via actual /extract. Raw search
    snippets alone never qualify; nor does raw_content from /search.
    """
    official_url = officeholder_authoritative_url(question)
    if official_url is None or official_url not in extracted_urls:
        return None

    for source in sources:
        if source.url != official_url or not source.excerpt:
            continue
        page = _clean_official_page(source.excerpt)
        if official_url == "https://www.whitehouse.gov/administration/":
            found = _US_ADMINISTRATION_HEADING.search(page)
            if found:
                name = found.group(1).strip()
                return (
                    f"The current U.S. president is {name}. {source.citation}",
                    source,
                )
        elif official_url == "https://pmo.gov.bd/":
            found = _BD_PRIME_MINISTER_LABEL.search(page)
            if found:
                name = " ".join(found.group(1).split())
                # Preserve the spelling published by the government's own
                # page rather than hallucinating a transliteration.
                return (
                    "The current Prime Minister of Bangladesh is "
                    f"{name}. {source.citation}",
                    source,
                )
    return None
