from collections.abc import Sequence
from typing import Any

from openai import OpenAI

from app.embeddings.types import (
    EmbeddingProviderInfo,
    EmbeddingProviderRequestError,
    EmbeddingValidationError,
)
from app.embeddings.validation import (
    validate_embedding_vector,
    validate_text_batch,
)


class OpenAIEmbeddingProvider:
    """
    Production embedding provider backed by
    the OpenAI Embeddings API.
    """

    def __init__(
        self,
        *,
        api_key: str,
        model_name: str = (
            "text-embedding-3-small"
        ),
        dimension: int = 384,
        max_batch_size: int = 128,
        timeout_seconds: float = 30.0,
        max_retries: int = 3,
        client: Any | None = None,
    ) -> None:
        if client is None and not api_key.strip():
            raise EmbeddingValidationError(
                "OpenAI API key cannot be empty"
            )

        self._info = EmbeddingProviderInfo(
            provider_name="openai",
            model_name=model_name,
            dimension=dimension,
            max_batch_size=max_batch_size,
        )

        self._client = (
            client
            if client is not None
            else OpenAI(
                api_key=api_key,
                timeout=timeout_seconds,
                max_retries=max_retries,
            )
        )

    @property
    def info(
        self,
    ) -> EmbeddingProviderInfo:
        return self._info

    def embed_documents(
        self,
        texts: Sequence[str],
    ) -> list[list[float]]:
        validated_texts = validate_text_batch(
            texts=texts,
            max_batch_size=(
                self.info.max_batch_size
            ),
        )

        try:
            response = (
                self._client
                .embeddings
                .create(
                    model=self.info.model_name,
                    input=list(validated_texts),
                    dimensions=(
                        self.info.dimension
                    ),
                    encoding_format="float",
                )
            )

        except Exception as exc:
            raise EmbeddingProviderRequestError(
                "OpenAI embedding request failed"
            ) from exc

        ordered_items = sorted(
            list(response.data),
            key=lambda item: int(
                item.index
            ),
        )

        if (
            len(ordered_items)
            != len(validated_texts)
        ):
            raise EmbeddingValidationError(
                "OpenAI returned an unexpected "
                "number of embeddings"
            )

        vectors: list[list[float]] = []

        for expected_index, item in enumerate(
            ordered_items
        ):
            received_index = int(
                item.index
            )

            if received_index != expected_index:
                raise EmbeddingValidationError(
                    "OpenAI embedding response "
                    "contains an invalid index"
                )

            vector = [
                float(value)
                for value in item.embedding
            ]

            validate_embedding_vector(
                vector=vector,
                expected_dimension=(
                    self.info.dimension
                ),
            )

            vectors.append(vector)

        return vectors

    def embed_query(
        self,
        text: str,
    ) -> list[float]:
        return self.embed_documents(
            [text]
        )[0]
