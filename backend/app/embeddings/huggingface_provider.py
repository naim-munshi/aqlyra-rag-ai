from collections.abc import Sequence
from typing import Any

from huggingface_hub import InferenceClient

from app.embeddings.types import (
    EmbeddingProviderInfo,
    EmbeddingProviderRequestError,
    EmbeddingValidationError,
)
from app.embeddings.validation import (
    normalize_vector,
    validate_embedding_vector,
    validate_text_batch,
)


DEFAULT_HF_EMBEDDING_MODEL = (
    "ibm-granite/"
    "granite-embedding-97m-multilingual-r2"
)


class HuggingFaceEmbeddingProvider:
    """
    Semantic embedding provider backed by Hugging Face
    Inference Providers.

    Output vectors are normalized locally so retrieval
    behavior does not depend on provider-side normalization.
    """

    def __init__(
        self,
        token: str,
        model_name: str = DEFAULT_HF_EMBEDDING_MODEL,
        dimension: int = 384,
        max_batch_size: int = 128,
        timeout_seconds: float = 30.0,
        *,
        client: Any | None = None,
    ) -> None:
        if client is None and not token.strip():
            raise EmbeddingValidationError(
                "Hugging Face token cannot be empty"
            )

        self._info = EmbeddingProviderInfo(
            provider_name="huggingface",
            model_name=model_name,
            dimension=dimension,
            max_batch_size=max_batch_size,
        )

        self._client = (
            client
            if client is not None
            else InferenceClient(
                token=token,
                timeout=timeout_seconds,
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
            max_batch_size=self.info.max_batch_size,
        )

        try:
            response = self._client.feature_extraction(
                list(validated_texts),
                model=self.info.model_name,
                truncate=True,
            )
        except Exception as exc:
            raise EmbeddingProviderRequestError(
                "Hugging Face embedding request failed"
            ) from exc

        raw_vectors = (
            response.tolist()
            if hasattr(response, "tolist")
            else response
        )

        if (
            raw_vectors
            and isinstance(
                raw_vectors[0],
                (int, float),
            )
        ):
            raw_vectors = [raw_vectors]

        if len(raw_vectors) != len(validated_texts):
            raise EmbeddingValidationError(
                "Hugging Face returned an unexpected "
                "number of embeddings"
            )

        vectors: list[list[float]] = []

        for raw_vector in raw_vectors:
            vector = normalize_vector(
                [
                    float(value)
                    for value in raw_vector
                ]
            )

            validate_embedding_vector(
                vector=vector,
                expected_dimension=self.info.dimension,
            )

            vectors.append(vector)

        return vectors

    def embed_query(
        self,
        text: str,
    ) -> list[float]:
        return self.embed_documents([text])[0]
