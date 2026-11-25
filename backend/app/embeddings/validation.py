import math
from collections.abc import Sequence

from app.embeddings.types import (
    EmbeddingValidationError,
)


def validate_text_batch(
    texts: Sequence[str],
    max_batch_size: int,
) -> tuple[str, ...]:
    if isinstance(
        texts,
        (str, bytes),
    ):
        raise EmbeddingValidationError(
            "Embedding input must be "
            "a sequence of strings"
        )

    normalized_batch = tuple(texts)

    if not normalized_batch:
        raise EmbeddingValidationError(
            "Embedding batch cannot be empty"
        )

    if len(normalized_batch) > max_batch_size:
        raise EmbeddingValidationError(
            "Embedding batch exceeds "
            f"the maximum size of {max_batch_size}"
        )

    for index, text in enumerate(
        normalized_batch
    ):
        if not isinstance(text, str):
            raise EmbeddingValidationError(
                "Embedding text at index "
                f"{index} is not a string"
            )

        if not text.strip():
            raise EmbeddingValidationError(
                "Embedding text at index "
                f"{index} cannot be empty"
            )

    return normalized_batch


def normalize_vector(
    values: list[float],
) -> list[float]:
    """Normalize without overflowing for finite high-magnitude vectors.

    Dividing the raw values by sqrt(sum(x*x)) can overflow even when the
    direction is perfectly valid. Scale first; this preserves orientation
    and the existing embedding dimension/model contract.
    """
    if not values:
        raise EmbeddingValidationError(
            "Embedding vector magnitude cannot be zero"
        )

    for value in values:
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
        ):
            raise EmbeddingValidationError(
                "Embedding vector contains an invalid numeric value"
            )

    scale = max(abs(value) for value in values)
    if scale == 0:
        raise EmbeddingValidationError(
            "Embedding vector magnitude cannot be zero"
        )
    scaled = [value / scale for value in values]
    scaled_magnitude = math.sqrt(
        math.fsum(value * value for value in scaled)
    )
    return [value / scaled_magnitude for value in scaled]


def validate_embedding_vector(
    vector: Sequence[float],
    expected_dimension: int,
) -> None:
    if len(vector) != expected_dimension:
        raise EmbeddingValidationError(
            "Embedding dimension mismatch: "
            f"expected {expected_dimension}, "
            f"received {len(vector)}"
        )

    for index, value in enumerate(vector):
        if not isinstance(
            value,
            (int, float),
        ):
            raise EmbeddingValidationError(
                "Embedding value at index "
                f"{index} is not numeric"
            )

        if not math.isfinite(value):
            raise EmbeddingValidationError(
                "Embedding value at index "
                f"{index} is not finite"
            )
