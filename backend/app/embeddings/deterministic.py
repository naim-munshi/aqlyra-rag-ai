import hashlib
from collections.abc import Sequence

from app.embeddings.types import (
    EmbeddingProviderInfo,
)
from app.embeddings.validation import (
    normalize_vector,
    validate_embedding_vector,
    validate_text_batch,
)


class DeterministicHashEmbeddingProvider:
    """
    Deterministic embedding provider for tests and development.

    This provider does not produce semantic embeddings.
    It exists to test batching, persistence, retrieval plumbing,
    dimensions, and provider contracts without external API cost.
    """

    def __init__(
        self,
        dimension: int = 384,
        max_batch_size: int = 128,
    ) -> None:
        self._info = EmbeddingProviderInfo(
            provider_name="deterministic",
            model_name="deterministic-sha256-v1",
            dimension=dimension,
            max_batch_size=max_batch_size,
        )

    @property
    def info(self) -> EmbeddingProviderInfo:
        return self._info

    def _embed_text(
        self,
        text: str,
    ) -> list[float]:
        values: list[float] = []
        counter = 0

        while len(values) < self.info.dimension:
            digest_input = (
                f"{counter}\x00{text}"
            ).encode("utf-8")

            digest = hashlib.sha256(
                digest_input
            ).digest()

            values.extend(
                (
                    byte_value / 127.5
                ) - 1.0
                for byte_value in digest
            )

            counter += 1

        vector = normalize_vector(
            values[:self.info.dimension]
        )

        validate_embedding_vector(
            vector=vector,
            expected_dimension=(
                self.info.dimension
            ),
        )

        return vector

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

        return [
            self._embed_text(text)
            for text in validated_texts
        ]

    def embed_query(
        self,
        text: str,
    ) -> list[float]:
        return self.embed_documents(
            [text]
        )[0]
