import math

import pytest

from app.embeddings.huggingface_provider import (
    HuggingFaceEmbeddingProvider,
)
from app.embeddings.registry import (
    create_embedding_provider,
)
from app.embeddings.types import (
    EmbeddingProviderRequestError,
    EmbeddingValidationError,
)


class FakeHFClient:
    def __init__(
        self,
        response,
    ) -> None:
        self.response = response
        self.calls = []

    def feature_extraction(
        self,
        text,
        **kwargs,
    ):
        self.calls.append(
            {
                "text": text,
                **kwargs,
            }
        )
        return self.response


class FailingHFClient:
    def feature_extraction(
        self,
        text,
        **kwargs,
    ):
        raise RuntimeError("provider failed")


def test_huggingface_provider_embeds_batch(
) -> None:
    client = FakeHFClient(
        [
            [3.0, 4.0, 0.0, 0.0],
            [0.0, 0.0, 5.0, 12.0],
        ]
    )

    provider = HuggingFaceEmbeddingProvider(
        token="test-token",
        model_name="test-model",
        dimension=4,
        max_batch_size=8,
        client=client,
    )

    vectors = provider.embed_documents(
        [
            "first document",
            "second document",
        ]
    )

    assert provider.info.provider_name == "huggingface"
    assert provider.info.model_name == "test-model"
    assert len(vectors) == 2
    assert all(len(vector) == 4 for vector in vectors)

    for vector in vectors:
        norm = math.sqrt(
            sum(value * value for value in vector)
        )
        assert norm == pytest.approx(1.0)

    assert client.calls[0]["model"] == "test-model"
    assert client.calls[0]["truncate"] is True


def test_huggingface_provider_embeds_query(
) -> None:
    client = FakeHFClient(
        [[1.0, 0.0, 0.0, 0.0]]
    )

    provider = HuggingFaceEmbeddingProvider(
        token="test-token",
        model_name="test-model",
        dimension=4,
        client=client,
    )

    vector = provider.embed_query(
        "semantic search"
    )

    assert vector == pytest.approx(
        [1.0, 0.0, 0.0, 0.0]
    )


def test_huggingface_provider_requires_token(
) -> None:
    with pytest.raises(
        EmbeddingValidationError,
    ):
        HuggingFaceEmbeddingProvider(
            token="",
        )


def test_huggingface_provider_wraps_request_error(
) -> None:
    provider = HuggingFaceEmbeddingProvider(
        token="test-token",
        model_name="test-model",
        dimension=4,
        client=FailingHFClient(),
    )

    with pytest.raises(
        EmbeddingProviderRequestError,
    ):
        provider.embed_query("query")


def test_registry_creates_huggingface_provider(
) -> None:
    client = FakeHFClient(
        [[1.0, 0.0, 0.0, 0.0]]
    )

    provider = create_embedding_provider(
        provider_name="huggingface",
        model_name="test-model",
        dimension=4,
        hf_token="test-token",
        client=client,
    )

    assert isinstance(
        provider,
        HuggingFaceEmbeddingProvider,
    )
    assert provider.info.dimension == 4
