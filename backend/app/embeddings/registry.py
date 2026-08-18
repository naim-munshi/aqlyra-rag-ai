from typing import Any

from app.config.settings import settings
from app.embeddings.deterministic import (
    DeterministicHashEmbeddingProvider,
)
from app.embeddings.openai_provider import (
    OpenAIEmbeddingProvider,
)
from app.embeddings.huggingface_provider import (
    DEFAULT_HF_EMBEDDING_MODEL,
    HuggingFaceEmbeddingProvider,
)
from app.embeddings.types import (
    EmbeddingProvider,
    EmbeddingProviderNotFoundError,
)


def create_embedding_provider(
    provider_name: str = "deterministic",
    dimension: int = 384,
    max_batch_size: int = 128,
    *,
    model_name: str | None = None,
    api_key: str = "",
    hf_token: str = "",
    timeout_seconds: float = 30.0,
    max_retries: int = 3,
    client: Any | None = None,
) -> EmbeddingProvider:
    normalized_name = (
        provider_name
        .strip()
        .lower()
    )

    if normalized_name == "deterministic":
        return (
            DeterministicHashEmbeddingProvider(
                dimension=dimension,
                max_batch_size=max_batch_size,
            )
        )

    if normalized_name == "huggingface":
        return HuggingFaceEmbeddingProvider(
            token=hf_token,
            model_name=(
                model_name
                or DEFAULT_HF_EMBEDDING_MODEL
            ),
            dimension=dimension,
            max_batch_size=max_batch_size,
            timeout_seconds=timeout_seconds,
            client=client,
        )

    if normalized_name == "openai":
        return OpenAIEmbeddingProvider(
            api_key=api_key,
            model_name=(
                model_name
                or "text-embedding-3-small"
            ),
            dimension=dimension,
            max_batch_size=max_batch_size,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            client=client,
        )

    raise EmbeddingProviderNotFoundError(
        "Unknown embedding provider: "
        f"{provider_name}"
    )


def create_configured_embedding_provider(
) -> EmbeddingProvider:
    return create_embedding_provider(
        provider_name=(
            settings.EMBEDDING_PROVIDER
        ),
        model_name=(
            settings.EMBEDDING_MODEL
        ),
        dimension=(
            settings.EMBEDDING_DIMENSION
        ),
        max_batch_size=(
            settings.EMBEDDING_MAX_BATCH_SIZE
        ),
        api_key=settings.OPENAI_API_KEY,
        hf_token=settings.HF_TOKEN,
        timeout_seconds=(
            settings.EMBEDDING_TIMEOUT_SECONDS
        ),
        max_retries=(
            settings.EMBEDDING_MAX_RETRIES
        ),
    )
