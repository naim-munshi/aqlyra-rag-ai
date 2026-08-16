import re
import unicodedata
from dataclasses import dataclass
from enum import Enum


class ProductIdentityIntent(
    str,
    Enum,
):
    SELF_IDENTITY = "self_identity"
    FOUNDER = "founder"
    CREATOR = "creator"
    PLATFORM_IDENTITY = "platform_identity"
    EXECUTIVE_ROLE = "executive_role"


@dataclass(
    frozen=True,
    slots=True,
)
class ProductIdentityMatch:
    intent: ProductIdentityIntent
    language: str


_SECOND_PERSON_LATIN = frozenset(
    {
        "you",
        "your",
        "yourself",
        "tumi",
        "tomar",
        "tumar",
        "tomake",
        "tumake",
    }
)

_FOUNDER_LATIN = frozenset(
    {
        "founder",
        "founded",
        "founding",
        "protisthata",
        "prothisthata",
    }
)

_CREATOR_LATIN = frozenset(
    {
        "creator",
        "created",
        "made",
        "built",
        "banaise",
        "banayse",
        "baniyeche",
        "banieche",
    }
)

_EXECUTIVE_LATIN = frozenset(
    {
        "ceo",
        "owner",
        "malik",
    }
)

_PLATFORM_LATIN = frozenset(
    {
        "chatgpt",
        "openai",
        "gpt",
        "groq",
        "deepseek",
        "claude",
        "gemini",
    }
)

_BANGLISH_MARKERS = frozenset(
    {
        "tumi",
        "tomar",
        "tumar",
        "tomake",
        "tumake",
        "ke",
        "ki",
        "banaise",
        "banayse",
        "baniyeche",
        "banieche",
        "protisthata",
        "prothisthata",
    }
)

_BENGALI_SECOND_PERSON = (
    "তুমি",
    "তোমার",
    "তোমাকে",
)

_BENGALI_FOUNDER = (
    "প্রতিষ্ঠাতা",
)

_BENGALI_CREATOR = (
    "নির্মাতা",
    "তৈরি",
    "বানিয়েছে",
    "বানিয়েছে",
    "বানিয়েছে",
    "বানানো",
)

_BENGALI_EXECUTIVE = (
    "মালিক",
)


def _normalize(
    value: str,
) -> str:
    normalized = unicodedata.normalize(
        "NFKC",
        value,
    ).casefold()

    return " ".join(
        normalized.split()
    )


def _latin_tokens(
    normalized: str,
) -> set[str]:
    return set(
        re.findall(
            r"[a-z0-9]+",
            normalized,
        )
    )


def _contains_any(
    text: str,
    terms: tuple[str, ...],
) -> bool:
    return any(
        term in text
        for term in terms
    )


def _has_bengali(
    value: str,
) -> bool:
    return any(
        "\u0980" <= char <= "\u09ff"
        for char in value
    )


def _language(
    original: str,
    tokens: set[str],
) -> str:
    if _has_bengali(original):
        return "bn"

    if tokens & _BANGLISH_MARKERS:
        return "bn"

    return "en"


def detect_product_identity_intent(
    message: str,
) -> ProductIdentityMatch | None:
    normalized = _normalize(message)

    if not normalized:
        return None

    tokens = _latin_tokens(
        normalized
    )

    language = _language(
        message,
        tokens,
    )

    has_aqlyra = (
        "aqlyra" in tokens
        or "aqlyra" in normalized
    )

    has_second_person = (
        bool(
            tokens
            & _SECOND_PERSON_LATIN
        )
        or _contains_any(
            normalized,
            _BENGALI_SECOND_PERSON,
        )
    )

    identity_anchor = (
        has_aqlyra
        or has_second_person
    )

    if not identity_anchor:
        return None

    has_executive_signal = (
        bool(
            tokens
            & _EXECUTIVE_LATIN
        )
        or _contains_any(
            normalized,
            _BENGALI_EXECUTIVE,
        )
    )

    if has_executive_signal:
        return ProductIdentityMatch(
            intent=(
                ProductIdentityIntent
                .EXECUTIVE_ROLE
            ),
            language=language,
        )

    has_founder_signal = (
        bool(
            tokens
            & _FOUNDER_LATIN
        )
        or _contains_any(
            normalized,
            _BENGALI_FOUNDER,
        )
    )

    if has_founder_signal:
        return ProductIdentityMatch(
            intent=(
                ProductIdentityIntent
                .FOUNDER
            ),
            language=language,
        )

    has_creator_signal = (
        bool(
            tokens
            & _CREATOR_LATIN
        )
        or _contains_any(
            normalized,
            _BENGALI_CREATOR,
        )
        or (
            has_aqlyra
            and "behind" in tokens
        )
    )

    if has_creator_signal:
        return ProductIdentityMatch(
            intent=(
                ProductIdentityIntent
                .CREATOR
            ),
            language=language,
        )

    if (
        has_second_person
        and bool(
            tokens
            & _PLATFORM_LATIN
        )
    ):
        return ProductIdentityMatch(
            intent=(
                ProductIdentityIntent
                .PLATFORM_IDENTITY
            ),
            language=language,
        )

    compact = re.sub(
        r"[^a-z0-9\u0980-\u09ff]+",
        " ",
        normalized,
    )

    compact = " ".join(
        compact.split()
    )

    self_identity_phrases = {
        "who are you",
        "what are you",
        "what is your name",
        "whats your name",
        "your name",
        "who is aqlyra",
        "what is aqlyra",
        "tumi ke",
        "tomar nam ki",
        "tumar nam ki",
        "তুমি কে",
        "তোমার নাম কি",
        "তোমার নাম কী",
    }

    if compact in self_identity_phrases:
        return ProductIdentityMatch(
            intent=(
                ProductIdentityIntent
                .SELF_IDENTITY
            ),
            language=language,
        )

    return None
