from app.embeddings.deterministic import (
    DeterministicHashEmbeddingProvider,
)
from app.embeddings.types import (
    EmbeddingProvider,
    EmbeddingProviderNotFoundError,
)


def create_embedding_provider(
    provider_name: str = "deterministic",
    dimension: int = 384,
    max_batch_size: int = 128,
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

    raise EmbeddingProviderNotFoundError(
        "Unknown embedding provider: "
        f"{provider_name}"
    )
