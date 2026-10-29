from collections.abc import Iterator

from app.llms.types import (
    LLMGeneration,
    LLMProviderInfo,
    LLMStreamEvent,
)
from app.product_identity.facts import (
    PRODUCT_CREATOR,
    PRODUCT_FOUNDER,
    PRODUCT_IDENTITY_MODEL_NAME,
    PRODUCT_IDENTITY_PROVIDER_NAME,
    PRODUCT_NAME,
)
from app.product_identity.intent import (
    ProductIdentityIntent,
    detect_product_identity_intent,
)


def resolve_product_identity_answer(
    message: str,
) -> str | None:
    match = detect_product_identity_intent(
        message
    )

    if match is None:
        return None

    bengali = (
        match.language == "bn"
    )

    if (
        match.intent
        == ProductIdentityIntent.FOUNDER
    ):
        if bengali:
            return (
                f"{PRODUCT_NAME}-এর প্রতিষ্ঠাতা "
                f"ও নির্মাতা {PRODUCT_FOUNDER}।"
            )

        return (
            f"{PRODUCT_NAME} was founded by "
            f"{PRODUCT_FOUNDER}."
        )

    if (
        match.intent
        == ProductIdentityIntent.CREATOR
    ):
        if bengali:
            return (
                f"{PRODUCT_NAME}-এর প্রতিষ্ঠাতা "
                f"ও নির্মাতা {PRODUCT_CREATOR}।"
            )

        return (
            f"I'm {PRODUCT_NAME}, created by "
            f"{PRODUCT_CREATOR}."
        )

    if (
        match.intent
        == ProductIdentityIntent
        .PLATFORM_IDENTITY
    ):
        if bengali:
            return (
                f"না। আমি {PRODUCT_NAME}।"
            )

        return (
            f"No. I'm {PRODUCT_NAME}."
        )

    if (
        match.intent
        == ProductIdentityIntent
        .EXECUTIVE_ROLE
    ):
        if bengali:
            return (
                f"{PRODUCT_NAME}-এর প্রতিষ্ঠাতা "
                f"ও নির্মাতা {PRODUCT_FOUNDER}। "
                "Owner বা CEO পরিচয় বর্তমানে "
                "configured নয়।"
            )

        return (
            f"{PRODUCT_NAME} was founded and "
            f"created by {PRODUCT_FOUNDER}. "
            "Owner and CEO identities are not "
            "currently configured."
        )

    if bengali:
        return (
            f"আমি {PRODUCT_NAME}, "
            "একটি AI assistant।"
        )

    return (
        f"I'm {PRODUCT_NAME}, "
        "an AI assistant."
    )


def resolve_founder_followup_answer(
    message: str,
    *,
    last_assistant_content: str | None,
) -> str | None:
    """Answer a *contextual* founder follow-up using only verified product facts.

    Never treat an unrelated personal question as referring to Aqlyra's founder:
    the immediately preceding assistant turn must identify Md Naim as the
    founder/creator, unless the current question explicitly names Md Naim and
    Aqlyra together.
    """
    import re

    normalized = " ".join(message.casefold().split())
    named_founder = (
        "md naim" in normalized and "aqlyra" in normalized
    )
    previous = last_assistant_content or ""
    founder_context = (
        "md naim" in previous.casefold()
        and "aqlyra" in previous.casefold()
        and any(term in previous.casefold() for term in (
            "প্রতিষ্ঠাতা", "নির্মাতা", "founder", "founded", "created",
        ))
    )
    if not (named_founder or founder_context):
        return None

    work = any(term in normalized for term in (
        "কাজ", "কি করে", "কী করেন", "পেশা", "work", "job",
        "profession", "ki kore", "kaj kore",
    ))
    location = any(term in normalized for term in (
        "কোথায় থাক", "কোথায় থাক", "বাসা", "বাড়ি", "বাড়ি",
        "where does", "where is he living", "live",
        "address", "kothay thake",
    ))
    if not (work or location):
        return None

    has_referent = named_founder or bool(re.search(
        r"(?<![a-z])(he|him|his|naim|md)(?![a-z])", normalized
    )) or any(term in normalized for term in (
        "সে", "তিনি", "উনি", "তার", "তাঁর",
    ))
    if not has_referent:
        return None

    bengali = any("\u0980" <= char <= "\u09ff" for char in message)
    if bengali:
        details = []
        if work:
            details.append(
                "Md Naim Aqlyra-এর প্রতিষ্ঠাতা ও নির্মাতা। "
                "তিনি Aqlyra-এর AI ও RAG সফটওয়্যার তৈরির কাজ করেন।"
            )
        if location:
            details.append(
                "তাঁর ব্যক্তিগত বাসস্থান সম্পর্কে যাচাই করা প্রকাশ্য "
                "তথ্য নেই, তাই কোনো ঠিকানা অনুমান করে বলব না।"
            )
        return " ".join(details)

    details = []
    if work:
        details.append(
            "Md Naim founded and builds Aqlyra, an AI and RAG "
            "software platform."
        )
    if location:
        details.append(
            "There is no verified public residential location for "
            "him in Aqlyra's product information, so I won't guess."
        )
    return " ".join(details)


class ProductIdentityLLMProvider:
    def __init__(
        self,
        response_text: str,
    ) -> None:
        self._response_text = (
            response_text.strip()
        )

        self._info = LLMProviderInfo(
            provider_name=(
                PRODUCT_IDENTITY_PROVIDER_NAME
            ),
            model_name=(
                PRODUCT_IDENTITY_MODEL_NAME
            ),
            max_output_tokens=256,
        )

    @property
    def info(self) -> LLMProviderInfo:
        return self._info

    def _generation(
        self,
    ) -> LLMGeneration:
        return LLMGeneration(
            text=self._response_text,
            provider_name=(
                self.info.provider_name
            ),
            model_name=(
                self.info.model_name
            ),
            response_id=None,
            input_tokens=None,
            output_tokens=None,
            total_tokens=None,
        )

    def generate(
        self,
        *,
        instructions: str,
        input_text: str,
    ) -> LLMGeneration:
        return self._generation()

    def stream(
        self,
        *,
        instructions: str,
        input_text: str,
    ) -> Iterator[LLMStreamEvent]:
        generation = self._generation()

        yield LLMStreamEvent(
            event_type="delta",
            delta_text=(
                generation.text
            ),
        )

        yield LLMStreamEvent(
            event_type="complete",
            generation=generation,
        )
