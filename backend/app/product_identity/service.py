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
