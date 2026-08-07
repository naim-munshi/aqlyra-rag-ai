import math

import pytest

from app.embeddings import (
    DeterministicHashEmbeddingProvider,
    EmbeddingProviderNotFoundError,
    EmbeddingValidationError,
    create_embedding_provider,
)


def test_provider_exposes_stable_contract() -> None:
    provider = (
        DeterministicHashEmbeddingProvider(
            dimension=64,
            max_batch_size=16,
        )
    )

    assert (
        provider.info.provider_name
        == "deterministic"
    )

    assert (
        provider.info.model_name
        == "deterministic-sha256-v1"
    )

    assert provider.info.dimension == 64
    assert provider.info.max_batch_size == 16


def test_same_text_produces_same_embedding() -> None:
    provider = (
        DeterministicHashEmbeddingProvider(
            dimension=64
        )
    )

    first_vector = provider.embed_query(
        "Retrieval augmented generation"
    )

    second_vector = provider.embed_query(
        "Retrieval augmented generation"
    )

    assert first_vector == second_vector


def test_different_text_produces_different_embedding() -> None:
    provider = (
        DeterministicHashEmbeddingProvider(
            dimension=64
        )
    )

    first_vector = provider.embed_query(
        "Document retrieval"
    )

    second_vector = provider.embed_query(
        "Authentication security"
    )

    assert first_vector != second_vector


def test_embedding_has_correct_dimension_and_norm() -> None:
    provider = (
        DeterministicHashEmbeddingProvider(
            dimension=96
        )
    )

    vector = provider.embed_query(
        "Aqlyra RAG AI embedding pipeline"
    )

    magnitude = math.sqrt(
        sum(
            value * value
            for value in vector
        )
    )

    assert len(vector) == 96
    assert magnitude == pytest.approx(
        1.0,
        abs=1e-9,
    )


def test_batch_order_is_preserved() -> None:
    provider = (
        DeterministicHashEmbeddingProvider(
            dimension=32
        )
    )

    texts = [
        "First document",
        "Second document",
        "Third document",
    ]

    batch_vectors = (
        provider.embed_documents(texts)
    )

    individual_vectors = [
        provider.embed_query(text)
        for text in texts
    ]

    assert batch_vectors == individual_vectors


def test_empty_text_is_rejected() -> None:
    provider = (
        DeterministicHashEmbeddingProvider(
            dimension=32
        )
    )

    with pytest.raises(
        EmbeddingValidationError
    ):
        provider.embed_query("   ")


def test_unknown_provider_is_rejected() -> None:
    with pytest.raises(
        EmbeddingProviderNotFoundError
    ):
        create_embedding_provider(
            provider_name="unknown-provider"
        )
