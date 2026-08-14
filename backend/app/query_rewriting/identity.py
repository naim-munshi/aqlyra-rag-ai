from app.query_rewriting.types import (
    QueryRewriterInfo,
    QueryRewriteValidationError,
)


class IdentityQueryRewriter:
    @property
    def info(self) -> QueryRewriterInfo:
        return QueryRewriterInfo(
            provider_name="identity",
            model_name="identity-v1",
        )

    def rewrite(
        self,
        query: str,
    ) -> str:
        normalized = " ".join(
            query.split()
        )

        if not normalized:
            raise QueryRewriteValidationError(
                "Query cannot be empty"
            )

        return normalized
