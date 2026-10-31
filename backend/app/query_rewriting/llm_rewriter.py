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


_NEGATION_PATTERN = re.compile(
    r"\b(?:not|never|no|without|except|excluding|exclude|"
    r"cannot|can't|don't|doesn't|isn't|aren't|won't)\b"
    r"|(?<![\u0980-\u09ff])(?:না|নয়|নয়|নেই|ছাড়া|ছাড়া|বাদে)(?![\u0980-\u09ff])"
    r"|ない|ません|除く|以外",
    re.IGNORECASE,
)
_QUOTED_SPAN_PATTERN = re.compile(
    r'"([^"\n]{1,160})"|“([^”\n]{1,160})”|「([^」\n]{1,160})」'
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

    # Preserve the number of negated/excluded clauses. Presence alone
    # misses rewrites that silently drop "not B" from "not A and not B".
    # We allow synonyms (e.g. "not" -> "without"), but when a model
    # collapses/introduces exclusions we safely use the original query.
    original_negations = sum(1 for _ in _NEGATION_PATTERN.finditer(original))
    rewritten_negations = sum(1 for _ in _NEGATION_PATTERN.finditer(normalized))
    if original_negations != rewritten_negations:
        raise QueryRewriteValidationError(
            "Rewritten query changed exclusion or negation intent"
        )

    for match in _QUOTED_SPAN_PATTERN.finditer(original):
        phrase = _normalize_query(
            next(part for part in match.groups() if part is not None)
        )
        if phrase and phrase.casefold() not in normalized.casefold():
            raise QueryRewriteValidationError(
                "Rewritten query removed an exact quoted phrase"
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
