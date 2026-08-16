from app.product_identity import (
    PRODUCT_IDENTITY_MODEL_NAME,
    PRODUCT_IDENTITY_PROVIDER_NAME,
    ProductIdentityIntent,
    ProductIdentityLLMProvider,
    detect_product_identity_intent,
    resolve_product_identity_answer,
)


def test_detects_founder_variations() -> None:
    cases = (
        "Who founded Aqlyra?",
        "Who is the founder of Aqlyra?",
        "Who is behind Aqlyra's founding?",
        "Aqlyra founder ke?",
    )

    for message in cases:
        match = (
            detect_product_identity_intent(
                message
            )
        )

        assert match is not None
        assert (
            match.intent
            == ProductIdentityIntent.FOUNDER
        )


def test_detects_creator_variations() -> None:
    cases = (
        "Who created you?",
        "Who made Aqlyra?",
        "Who built you?",
        "Who is behind Aqlyra?",
        "Tomake ke banaise?",
        "তোমাকে কে তৈরি করেছে?",
    )

    for message in cases:
        match = (
            detect_product_identity_intent(
                message
            )
        )

        assert match is not None
        assert (
            match.intent
            == ProductIdentityIntent.CREATOR
        )


def test_detects_self_identity() -> None:
    cases = (
        "Who are you?",
        "What is your name?",
        "Tumi ke?",
        "তুমি কে?",
    )

    for message in cases:
        assert (
            detect_product_identity_intent(
                message
            )
            is not None
        )


def test_chatgpt_identity_is_rejected() -> None:
    answer = (
        resolve_product_identity_answer(
            "Are you ChatGPT?"
        )
    )

    assert answer == "No. I'm Aqlyra."
    assert "Md Naim" not in answer


def test_self_identity_does_not_leak_creator() -> None:
    answer = (
        resolve_product_identity_answer(
            "Who are you?"
        )
    )

    assert answer == (
        "I'm Aqlyra, an AI assistant."
    )

    assert "Md Naim" not in answer


def test_founder_answer_is_canonical() -> None:
    assert (
        resolve_product_identity_answer(
            "Who founded Aqlyra?"
        )
        == "Aqlyra was founded by Md Naim."
    )


def test_bengali_founder_answer() -> None:
    assert (
        resolve_product_identity_answer(
            "Aqlyra-এর প্রতিষ্ঠাতা কে?"
        )
        == (
            "Aqlyra-এর প্রতিষ্ঠাতা ও "
            "নির্মাতা Md Naim।"
        )
    )


def test_owner_and_ceo_are_not_invented() -> None:
    answer = (
        resolve_product_identity_answer(
            "Who is the CEO of Aqlyra?"
        )
    )

    assert answer is not None
    assert "Md Naim" in answer
    assert "not" in answer.lower()


def test_unrelated_question_is_not_routed() -> None:
    assert (
        resolve_product_identity_answer(
            "Explain Python decorators"
        )
        is None
    )

    assert (
        resolve_product_identity_answer(
            "Who founded OpenAI?"
        )
        is None
    )


def test_unrelated_behind_phrase_is_not_identity() -> None:
    assert (
        resolve_product_identity_answer(
            "What is behind your recommendation?"
        )
        is None
    )


def test_identity_provider_metadata() -> None:
    provider = (
        ProductIdentityLLMProvider(
            "Aqlyra identity answer."
        )
    )

    assert (
        provider.info.provider_name
        == PRODUCT_IDENTITY_PROVIDER_NAME
    )

    assert (
        provider.info.model_name
        == PRODUCT_IDENTITY_MODEL_NAME
    )


def test_identity_provider_stream_contract() -> None:
    provider = (
        ProductIdentityLLMProvider(
            "Aqlyra identity answer."
        )
    )

    events = list(
        provider.stream(
            instructions="Identity.",
            input_text="Who are you?",
        )
    )

    assert len(events) == 2

    assert events[0].event_type == "delta"
    assert events[0].delta_text == (
        "Aqlyra identity answer."
    )

    assert (
        events[1].event_type
        == "complete"
    )

    assert (
        events[1].generation
        is not None
    )

    assert (
        events[1].generation.text
        == "Aqlyra identity answer."
    )
