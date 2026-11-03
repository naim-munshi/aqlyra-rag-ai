"""Small verified-current-office fact lane; never infer a name from a title alone.

First-party evidence must be from live /extract page text. The current
government directory is independently verified, and the parser never stores
or hardcodes a politician's identity. Rich "about" requests use normal
evidence-grounded synthesis rather than this one-line shortcut.
"""
from __future__ import annotations

import re
from urllib.parse import urlsplit

from app.schemas.web_research import WebResearchSource
from app.services.public_office_guard import officeholder_authoritative_url


_US_ADMINISTRATION_HEADING = re.compile(
    r"(?m)^(?:#{1,4}\s*)?President\s+"
    r"([A-Z][A-Za-z.'-]+(?:\s+(?:[A-Z][A-Za-z.'-]+|[A-Z]\.)){1,4})"
    r"\s*$"
)
_BD_NAME = r"([\u0980-\u09ff]{2,}(?:\s+[\u0980-\u09ff]{2,}){1,4})"
_BD_PRIME_MINISTER_LABEL = re.compile(
    r"জনাব\s+" + _BD_NAME
    + r"\s*(?:\n|\|)\s*(?:মাননীয়\s+)?প্রধানমন্ত্রী(?=\s|$|[।|])"
)
_BD_PRIME_MINISTER_HEADING = re.compile(
    r"(?m)^(?:#{1,4}\s*)?প্রধানমন্ত্রী\s*(?:\n|:)\s*"
    r"(?:Image(?::[^\n]*)?\s*\n\s*)?"
    r"জনাব\s+" + _BD_NAME
    + r"(?:\s+বিস্তারিত)?(?=\n|\s*$)"
)


def _is_verified_bd_current_office_url(url: str) -> bool:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.username or parsed.password:
        return False
    host = (parsed.hostname or "").lower()
    if host == "pmo.gov.bd":
        return parsed.path in ("", "/")
    if host == "cabinet.gov.bd":
        return parsed.path in ("", "/") or parsed.path.startswith(
            ("/pages/office-heads/", "/pages/static-pages/")
        )
    return False


def _extract_current_bd_name(page_text: str) -> str | None:
    page = page_text.replace("\r\n", "\n").replace("\r", "\n")
    for pattern in (_BD_PRIME_MINISTER_LABEL, _BD_PRIME_MINISTER_HEADING):
        match = pattern.search(page)
        if match:
            name = " ".join(match.group(1).split())
            if "প্রাক্তন" not in name and "সাবেক" not in name:
                return name
    return None


def verified_officeholder_fast_answer(
    question: str,
    sources: list[WebResearchSource],
    *,
    extracted_urls: set[str],
    official_page_text: str | None = None,
    official_page_text_by_url: dict[str, str] | None = None,
) -> tuple[str, WebResearchSource] | None:
    """Use only authoritative, freshly extracted text, never search snippets."""
    official_url = officeholder_authoritative_url(question)
    if not official_url:
        return None
    pages = official_page_text_by_url or {}

    if official_url == "https://www.whitehouse.gov/administration/":
        for source in sources:
            if source.url != official_url or source.url not in extracted_urls:
                continue
            page = pages.get(source.url) or official_page_text or source.excerpt
            match = _US_ADMINISTRATION_HEADING.search(
                page.replace("\r\n", "\n").replace("\r", "\n")
            )
            if match:
                return (
                    f"The current U.S. president is {match.group(1).strip()}. "
                    f"{source.citation}",
                    source,
                )
        return None

    if official_url == "https://pmo.gov.bd/":
        validated: list[tuple[str, WebResearchSource]] = []
        for source in sources:
            if (
                source.url not in extracted_urls
                or not _is_verified_bd_current_office_url(source.url)
            ):
                continue
            page = pages.get(source.url) or (
                official_page_text if source.url == official_url else None
            ) or source.excerpt
            name = _extract_current_bd_name(page)
            if name:
                validated.append((name, source))
        # If independent official pages conflict, avoid an unsourced guess.
        if len({name for name, _ in validated}) == 1 and validated:
            name, source = validated[0]
            return (
                f"The current Prime Minister of Bangladesh is {name}. "
                f"{source.citation}",
                source,
            )
    return None
