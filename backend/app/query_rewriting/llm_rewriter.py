import re

from app.llms import (
    LLMError,
    LLMProvider,
)
from app.query_rewriting.types import (
    QueryRewriterInfo,
    QueryRewriteError,
    QueryRewriteValidationError,
)


DEFAULT_MAX_REWRITE_CHARS = 500

_PROTECTED_TOKEN_PATTERN = re.compile(
    r"""
    (?<!\w)
    (?=
        [A-Za-z0-9./:%-]*\d
    )
    [A-Za-z0-9]+
    (?:
        [.:/%-]
        [A-Za-z0-9]+
    )*
    (?!\w)
    """,
    flags=re.VERBOSE,
)


_REWRITE_INSTRUCTIONS = """
You optimize user questions for document retrieval.

Rewrite the input into one concise search query.

Rules:
- Preserve the original meaning.
- Preserve every identifier, code, number, date, time,
  percentage, version, measurement, and technical token.
- Preserve important proper nouns and domain terminology.
- Do not answer the question.
- Do not add facts.
- Do not invent synonyms that change meaning.
- Keep the same language as the input.
- Return only the rewritten search query.
- Return exactly one line.
""".strip()


def _normalize_query(
    text: str,
) -> str:
    return " ".join(
        text.split()
    )


def _protected_tokens(
    text: str,
) -> tuple[str, ...]:
    tokens: list[str] = []
    seen: set[str] = set()

    for match in (
        _PROTECTED_TOKEN_PATTERN
        .finditer(text)
    ):
        token = match.group(0)
        normalized = token.casefold()

        if normalized in seen:
            continue

        seen.add(normalized)
        tokens.append(token)

    return tuple(tokens)


def _validate_rewrite(
    *,
    original: str,
    rewritten: str,
    max_chars: int,
) -> str:
    normalized = _normalize_query(
        rewritten
    )

    if not normalized:
        raise QueryRewriteValidationError(
            "Query rewriter returned an empty query"
        )

    if len(normalized) > max_chars:
        raise QueryRewriteValidationError(
            "Rewritten query exceeds maximum length"
        )

    original_tokens = {
        token.casefold(): token
        for token in _protected_tokens(
            original
        )
    }

    rewritten_tokens = {
        token.casefold(): token
        for token in _protected_tokens(
            normalized
        )
    }

    missing_tokens = [
        original_tokens[key]
        for key in original_tokens
        if key not in rewritten_tokens
    ]

    if missing_tokens:
        raise QueryRewriteValidationError(
            "Rewritten query removed protected "
            "tokens: "
            + ", ".join(missing_tokens)
        )

    added_tokens = [
        rewritten_tokens[key]
        for key in rewritten_tokens
        if key not in original_tokens
    ]

    if added_tokens:
        raise QueryRewriteValidationError(
            "Rewritten query added protected "
            "tokens: "
            + ", ".join(added_tokens)
        )

    return normalized


class LLMQueryRewriter:
    def __init__(
        self,
        *,
        provider: LLMProvider,
        max_chars: int = (
            DEFAULT_MAX_REWRITE_CHARS
        ),
    ) -> None:
        if max_chars < 1:
            raise QueryRewriteValidationError(
                "max_chars must be positive"
            )

        self._provider = provider
        self._max_chars = max_chars

    @property
    def info(self) -> QueryRewriterInfo:
        provider_info = (
            self._provider.info
        )

        return QueryRewriterInfo(
            provider_name=(
                f"llm:{provider_info.provider_name}"
            ),
            model_name=(
                provider_info.model_name
            ),
        )

    def rewrite(
        self,
        query: str,
    ) -> str:
        original = _normalize_query(
            query
        )

        if not original:
            raise QueryRewriteValidationError(
                "Query cannot be empty"
            )

        try:
            generation = (
                self._provider.generate(
                    instructions=(
                        _REWRITE_INSTRUCTIONS
                    ),
                    input_text=original,
                )
            )

        except LLMError as exc:
            raise QueryRewriteError(
                "Query rewrite provider failed"
            ) from exc

        return _validate_rewrite(
            original=original,
            rewritten=generation.text,
            max_chars=self._max_chars,
        )
