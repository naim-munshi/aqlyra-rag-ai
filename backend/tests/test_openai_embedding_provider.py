from typing import Any

import pytest

from app.embeddings import (
    EmbeddingProviderRequestError,
    EmbeddingValidationError,
    OpenAIEmbeddingProvider,
)


class FakeEmbeddingItem:
    def __init__(
        self,
        *,
        index: int,
        embedding: list[float],
    ) -> None:
        self.index = index
        self.embedding = embedding


class FakeEmbeddingResponse:
    def __init__(
        self,
        data: list[FakeEmbeddingItem],
    ) -> None:
        self.data = data


class FakeEmbeddingsResource:
    def __init__(
        self,
        *,
        response: FakeEmbeddingResponse
        | None = None,
        error: Exception | None = None,
    ) -> None:
        self.response = response
        self.error = error
        self.calls: list[
            dict[str, Any]
        ] = []

    def create(
        self,
        **kwargs: Any,
    ) -> FakeEmbeddingResponse:
        self.calls.append(kwargs)

        if self.error is not None:
            raise self.error

        assert self.response is not None

        return self.response


class FakeOpenAIClient:
    def __init__(
        self,
        embeddings: FakeEmbeddingsResource,
    ) -> None:
        self.embeddings = embeddings


def test_openai_provider_exposes_configuration(
) -> None:
    resource = FakeEmbeddingsResource(
        response=FakeEmbeddingResponse(
            data=[]
        )
    )

    provider = OpenAIEmbeddingProvider(
        api_key="",
        model_name=(
            "text-embedding-3-small"
        ),
        dimension=384,
        max_batch_size=32,
        client=FakeOpenAIClient(
            resource
        ),
    )

    assert (
        provider.info.provider_name
        == "openai"
    )

    assert (
        provider.info.model_name
        == "text-embedding-3-small"
    )

    assert provider.info.dimension == 384
    assert provider.info.max_batch_size == 32


def test_openai_provider_sends_dimension_and_preserves_order(
) -> None:
    resource = FakeEmbeddingsResource(
        response=FakeEmbeddingResponse(
            data=[
                FakeEmbeddingItem(
                    index=1,
                    embedding=[
                        0.5,
                        0.6,
                        0.7,
                        0.8,
                    ],
                ),
                FakeEmbeddingItem(
                    index=0,
                    embedding=[
                        0.1,
                        0.2,
                        0.3,
                        0.4,
                    ],
                ),
            ]
        )
    )

    provider = OpenAIEmbeddingProvider(
        api_key="",
        dimension=4,
        max_batch_size=8,
        client=FakeOpenAIClient(
            resource
        ),
    )

    vectors = provider.embed_documents(
        [
            "First text",
            "Second text",
        ]
    )

    assert vectors == [
        [
            0.1,
            0.2,
            0.3,
            0.4,
        ],
        [
            0.5,
            0.6,
            0.7,
            0.8,
        ],
    ]

    assert len(resource.calls) == 1

    call = resource.calls[0]

    assert call["model"] == (
        "text-embedding-3-small"
    )

    assert call["input"] == [
        "First text",
        "Second text",
    ]

    assert call["dimensions"] == 4

    assert (
        call["encoding_format"]
        == "float"
    )


def test_openai_provider_rejects_wrong_dimension(
) -> None:
    resource = FakeEmbeddingsResource(
        response=FakeEmbeddingResponse(
            data=[
                FakeEmbeddingItem(
                    index=0,
                    embedding=[
                        0.1,
                        0.2,
                        0.3,
                    ],
                )
            ]
        )
    )

    provider = OpenAIEmbeddingProvider(
        api_key="",
        dimension=4,
        client=FakeOpenAIClient(
            resource
        ),
    )

    with pytest.raises(
        EmbeddingValidationError
    ):
        provider.embed_query(
            "Dimension validation"
        )


def test_openai_provider_wraps_request_failure(
) -> None:
    resource = FakeEmbeddingsResource(
        error=RuntimeError(
            "Simulated network failure"
        )
    )

    provider = OpenAIEmbeddingProvider(
        api_key="",
        dimension=4,
        client=FakeOpenAIClient(
            resource
        ),
    )

    with pytest.raises(
        EmbeddingProviderRequestError
    ):
        provider.embed_query(
            "Request failure"
        )


def test_openai_provider_requires_api_key_without_client(
) -> None:
    with pytest.raises(
        EmbeddingValidationError
    ):
        OpenAIEmbeddingProvider(
            api_key="",
            dimension=384,
        )
