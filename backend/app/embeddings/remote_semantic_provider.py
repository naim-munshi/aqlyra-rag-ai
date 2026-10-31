"""Secure 384-d semantic embedding client for Aqlyra's own remote worker.

Provider is only activated with a pinned operator-owned Render HTTPS URL
and a long random token. No arbitrary user-supplied URLs or redirects.
"""
from collections.abc import Sequence
from typing import Any
from urllib.parse import urlsplit

import httpx

from app.embeddings.types import (
    EmbeddingProviderInfo, EmbeddingProviderRequestError,
    EmbeddingValidationError,
)
from app.embeddings.validation import (
    validate_text_batch, validate_embedding_vector, normalize_vector,
)

MODEL = "multilingual-e5-small-int8-v1"


class RemoteSemanticEmbeddingProvider:
    def __init__(
        self, *, base_url: str, api_token: str,
        dimension: int = 384, max_batch_size: int = 8,
        timeout_seconds: float = 90.0, client: Any | None = None,
    ):
        parsed = urlsplit(base_url.strip())
        host = (parsed.hostname or "").lower()
        if (
            parsed.scheme != "https"
            or not host.endswith(".onrender.com")
            or parsed.username is not None
            or parsed.password is not None
            or parsed.port not in (None, 443)
            or parsed.path not in ("", "/")
            or parsed.query or parsed.fragment
        ):
            raise EmbeddingValidationError("Semantic worker requires trusted Render HTTPS URL")
        if not api_token or len(api_token) < 32:
            raise EmbeddingValidationError("Semantic worker token missing or too short")
        if dimension != 384 or not 1 <= max_batch_size <= 8:
            raise EmbeddingValidationError("Unsupported semantic worker dimensions or batch size")
        self._base_url = base_url.rstrip("/")
        self._api_token = api_token
        self._client = client or httpx.Client(timeout=timeout_seconds, follow_redirects=False)
        self._info = EmbeddingProviderInfo(
            provider_name="remote_onnx", model_name=MODEL,
            dimension=384, max_batch_size=max_batch_size,
        )

    @property
    def info(self) -> EmbeddingProviderInfo:
        return self._info

    def _embed(self, texts: Sequence[str], mode: str) -> list[list[float]]:
        values = validate_text_batch(texts, self.info.max_batch_size)
        if any(len(text) > 6000 for text in values):
            raise EmbeddingValidationError("Embedding input exceeds 6000 characters")
        try:
            response = self._client.post(
                self._base_url + "/v1/embed",
                headers={"Authorization": "Bearer " + self._api_token},
                json={"texts": list(values), "mode": mode},
            )
            if response.status_code != 200:
                raise EmbeddingProviderRequestError(
                    "Isolated semantic worker returned an unavailable status"
                )
            body = response.json()
        except EmbeddingProviderRequestError:
            raise
        except Exception as exc:
            raise EmbeddingProviderRequestError(
                "Isolated semantic worker request failed"
            ) from exc
        if (
            not isinstance(body, dict)
            or body.get("model") != MODEL
            or body.get("dimension") != 384
            or not isinstance(body.get("vectors"), list)
            or len(body["vectors"]) != len(values)
        ):
            raise EmbeddingValidationError("Semantic worker response metadata mismatch")
        vectors: list[list[float]] = []
        for raw in body["vectors"]:
            if not isinstance(raw, list) or len(raw) != 384:
                raise EmbeddingValidationError("Invalid semantic vector dimension")
            vector = [float(v) for v in raw]
            validate_embedding_vector(vector, expected_dimension=384)
            vectors.append(normalize_vector(vector))
        return vectors

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return self._embed(texts, mode="passage")

    def embed_query(self, text: str) -> list[float]:
        return self._embed([text], mode="query")[0]
