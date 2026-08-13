from app.retrieval import RetrievalHit
from app.reranking.types import (
    RerankerInfo,
    RerankerScore,
    RerankerValidationError,
)


class IdentityReranker:
    """Preserve the existing candidate order."""

    def __init__(self) -> None:
        self._info = RerankerInfo(
            provider_name="identity",
            model_name="identity-reranker-v1",
        )

    @property
    def info(self) -> RerankerInfo:
        return self._info

    def rerank(
        self,
        *,
        query: str,
        hits: tuple[RetrievalHit, ...],
    ) -> tuple[RerankerScore, ...]:
        if not query.strip():
            raise RerankerValidationError(
                "Reranker query cannot be empty"
            )

        if not hits:
            return ()

        denominator = max(
            1,
            len(hits),
        )

        return tuple(
            RerankerScore(
                chunk_id=hit.chunk_id,
                score=(
                    1.0
                    - index / denominator
                ),
            )
            for index, hit in enumerate(hits)
        )
