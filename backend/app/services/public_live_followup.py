"""Privacy-safe follow-ups for public, time-sensitive web questions.

Only the current user-supplied coarse place is sent to public web research.
Previous messages are used locally to select a fixed public topic, never copied
into the external query. No device geolocation or private memory is accessed.
"""
from __future__ import annotations

import re

from app.services.auto_web_research_service import _NO_WEB, _PRIVATE_ONLY

_LOCATION_PREFIX = re.compile(
    r"^(?:(?:my\s+)?(?:location|city|country|region)\s*(?:is|:)\s*"
    r"|i\s*(?:am|'m)\s+in\s+|i\s+live\s+in\s+|in\s+)",
    re.IGNORECASE,
)
_BARE_COUNTRIES = frozenset({
    "japan", "日本", "bangladesh", "বাংলাদেশ", "india", "nepal",
    "united kingdom", "uk", "united states", "usa", "us",
    "australia", "canada", "germany", "france", "singapore",
})
_COUNTRIES = _BARE_COUNTRIES | {"bd", "jp"}
_PLACE = re.compile(
    r"[A-Za-z\u0980-\u09ff\u3040-\u30ff\u3400-\u9fff]"
    r"[A-Za-z\u0980-\u09ff\u3040-\u30ff\u3400-\u9fff ,.'-]{0,54}"
)
_PRIVATE_ADDRESS = re.compile(
    r"\b(?:street|road|avenue|apartment|unit|flat|house|home|"
    r"building|floor|room|postal|postcode|zipcode|zip|"
    r"address|password|secret|token|otp)\b"
    r"|住所|部屋|বাড়ি|বাসা|ঠিকানা",
    re.IGNORECASE,
)
_WEATHER = re.compile(
    r"\b(?:weather|forecast|temperature|rainfall|rain today)\b"
    r"|天気|天候|気温|天気予報|আবহাওয়া|আবহাওয়া|তাপমাত্রা",
    re.IGNORECASE,
)
_NEWS = re.compile(
    r"\b(?:news|headlines|breaking stories)\b"
    r"|ニュース|速報|খবর|সংবাদ",
    re.IGNORECASE,
)
_LOCATION_REQUEST = re.compile(
    r"\b(?:city|country|region|location|where|place|which area)\b"
    r"|都市|地域|場所|どこ|শহর|দেশ|কোথায়|কোথায়",
    re.IGNORECASE,
)


def _coarse_public_place(message: str) -> str | None:
    """Never route coordinates, street addresses, instructions or long text."""
    if _NO_WEB.search(message) or _PRIVATE_ONLY.search(message):
        return None
    plain = message.strip().strip("!?。। \"")
    match = _LOCATION_PREFIX.match(plain)
    place = plain[match.end():].strip() if match else plain
    place = place.rstrip(".।。 ").strip()
    if not 2 <= len(place) <= 55 or len(place.split()) > 5:
        return None
    if not _PLACE.fullmatch(place) or _PRIVATE_ADDRESS.search(place):
        return None
    # A bare reply is only interpreted as a place for recognized countries.
    # For cities, require an explicit location declaration (e.g. "in Tokyo").
    if match is None and place.casefold() not in _BARE_COUNTRIES:
        return None
    return place


def is_coarse_public_location_reply(message: str) -> bool:
    """Cheap gate: ordinary chat must never read prior messages for routing."""
    return _coarse_public_place(message) is not None


def public_live_location_followup(
    *, current_message: str, previous_user: str, previous_assistant: str,
) -> str | None:
    """Synthesize an independent public question, without past chat content."""
    place = _coarse_public_place(current_message)
    if place is None:
        return None
    if any(
        filter_.search(previous_user)
        for filter_ in (_NO_WEB, _PRIVATE_ONLY)
    ):
        return None
    # Only after a related, explicit location clarification, not a random
    # historic mention or model-generated recommendation.
    if not _LOCATION_REQUEST.search(previous_assistant):
        return None
    if _WEATHER.search(previous_user):
        if place.casefold() in _COUNTRIES:
            return (
                f"What is today's weather forecast across {place}? "
                "Give a country-wide overview; weather varies by city."
            )
        return f"What is today's weather and forecast in {place}?"
    if _NEWS.search(previous_user):
        return f"What are the latest public news headlines in {place} today?"
    return None
