"""Secure 384-d semantic embedding client for Aqlyra's own remote worker.

Provider is only activated with a pinned operator-owned Render HTTPS URL
and a long random token. No arbitrary user-supplied URLs or redirects.
"""
from collections.abc import Sequence
from dataclasses import dataclass, field
from functools import lru_cache
import hashlib
import logging
import threading
import time
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

MODEL = "bekko-static-multilingual-int8-mrl384-v1"

logger = logging.getLogger(__name__)
_TRANSIENT_STATUSES = frozenset({408, 425, 429, 500, 502, 503, 504})
_BREAKER_LOCK = threading.Lock()
_BREAKER_REGISTRY: dict[tuple[str, str], "_CircuitState"] = {}


@lru_cache(maxsize=8)
def _shared_http_client(timeout_seconds: float) -> httpx.Client:
    # Shared process-local httpx connection pooling reduces cold DNS/TLS
    # overhead and connection churn across many retrieval requests.
    return httpx.Client(
        timeout=min(timeout_seconds, 35.0),
        follow_redirects=False,
    )


@dataclass
class _CircuitState:
    consecutive_failures: int = 0
    open_until: float = 0.0
    lock: threading.Lock = field(default_factory=threading.Lock)


def _shared_circuit(endpoint: str, token: str) -> _CircuitState:
    # Distinguish operator-owned projects without retaining a plaintext
    # secret in the process-global circuit key.
    key = (endpoint, hashlib.sha256(token.encode("utf-8")).hexdigest())
    with _BREAKER_LOCK:
        return _BREAKER_REGISTRY.setdefault(key, _CircuitState())


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
        self._client = (
            client if client is not None else _shared_http_client(timeout_seconds)
        )
        # Ordinary provider construction occurs once per request. Production
        # circuit state must therefore survive distinct provider instances.
        # Injected test clients use isolated state to avoid cross-test leakage.
        self._circuit = (
            _CircuitState()
            if client is not None
            else _shared_circuit(self._base_url, api_token)
        )
        self._info = EmbeddingProviderInfo(
            provider_name="remote_onnx", model_name=MODEL,
            dimension=384, max_batch_size=max_batch_size,
        )

    @property
    def info(self) -> EmbeddingProviderInfo:
        return self._info

    def _check_circuit(self) -> None:
        with self._circuit.lock:
            if self._circuit.open_until > time.monotonic():
                raise EmbeddingProviderRequestError(
                    "Isolated semantic worker temporarily unavailable"
                )

    def _mark_success(self) -> None:
        with self._circuit.lock:
            self._circuit.consecutive_failures = 0
            self._circuit.open_until = 0.0

    def _mark_transient_failure(self) -> None:
        with self._circuit.lock:
            self._circuit.consecutive_failures += 1
            if self._circuit.consecutive_failures >= 3:
                self._circuit.open_until = time.monotonic() + 20.0
                logger.warning(
                    "remote_semantic_circuit_open duration_seconds=20"
                )

    def _mark_rate_limited(self, retry_after: str | None) -> None:
        """Open a bounded, shared cooldown after a provider/ingress HTTP 429.

        Retrying a clear quota response after 0.5 seconds multiplies calls
        and increases contention. Do not sleep on the request path, disclose
        upstream headers, or depend on untrusted Retry-After values.
        """
        seconds = 30
        if (
            retry_after is not None
            and len(retry_after) <= 6
            and retry_after.strip().isdigit()
        ):
            seconds = max(10, min(60, int(retry_after.strip())))
        with self._circuit.lock:
            self._circuit.consecutive_failures = max(
                3, self._circuit.consecutive_failures,
            )
            self._circuit.open_until = max(
                self._circuit.open_until,
                time.monotonic() + seconds,
            )
        logger.warning(
            "remote_semantic_rate_limit_circuit_open cooldown_seconds=%d",
            seconds,
        )

    def _embed(self, texts: Sequence[str], mode: str) -> list[list[float]]:
        values = validate_text_batch(texts, self.info.max_batch_size)
        if any(len(text) > 6000 for text in values):
            raise EmbeddingValidationError("Embedding input exceeds 6000 characters")
        self._check_circuit()
        # Retry only transient platform/cold-start responses. No retries for
        # 401/403/402, bad input or malformed vectors. Upper bound: two
        # HTTP requests and 0.5s backoff per embedding call.
        response = None
        for attempt in range(2):
            try:
                response = self._client.post(
                    self._base_url + "/v1/embed",
                    headers={"Authorization": "Bearer " + self._api_token},
                    json={"texts": list(values), "mode": mode},
                )
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                logger.warning(
                    "remote_semantic_transport_failure attempt=%d error_type=%s",
                    attempt + 1, type(exc).__name__,
                )
                if attempt == 0:
                    time.sleep(0.5)
                    continue
                self._mark_transient_failure()
                raise EmbeddingProviderRequestError(
                    "Isolated semantic worker request failed"
                ) from exc
            except Exception as exc:
                raise EmbeddingProviderRequestError(
                    "Isolated semantic worker request failed"
                ) from exc

            if response.status_code == 200:
                break
            if response.status_code == 429:
                # Render's ingress can return 429 before the embedding app
                # sees the request. One response is sufficient to back off.
                self._mark_rate_limited(response.headers.get("Retry-After"))
                raise EmbeddingProviderRequestError(
                    "Isolated semantic worker is temporarily rate limited"
                )
            if response.status_code not in _TRANSIENT_STATUSES:
                raise EmbeddingProviderRequestError(
                    "Isolated semantic worker returned a non-retryable status"
                )
            logger.warning(
                "remote_semantic_transient_status status=%d attempt=%d",
                response.status_code, attempt + 1,
            )
            if attempt == 0:
                time.sleep(0.5)
                continue
            self._mark_transient_failure()
            raise EmbeddingProviderRequestError(
                "Isolated semantic worker temporarily unavailable"
            )
        if response is None or response.status_code != 200:
            raise EmbeddingProviderRequestError(
                "Isolated semantic worker temporarily unavailable"
            )
        try:
            body = response.json()
        except (ValueError, TypeError) as exc:
            raise EmbeddingValidationError(
                "Isolated semantic worker returned invalid JSON"
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
            # JSON numbers only: reject strings, nulls and bools instead of
            # coercing malformed provider responses into semantic vectors.
            if any(
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                for value in raw
            ):
                raise EmbeddingValidationError(
                    "Semantic worker returned a nonnumeric vector"
                )
            try:
                vector = [float(value) for value in raw]
            except (TypeError, ValueError, OverflowError) as exc:
                raise EmbeddingValidationError(
                    "Semantic worker returned an invalid numeric vector"
                ) from exc
            validate_embedding_vector(vector, expected_dimension=384)
            normalized = normalize_vector(vector)
            validate_embedding_vector(normalized, expected_dimension=384)
            vectors.append(normalized)
        self._mark_success()
        return vectors

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return self._embed(texts, mode="passage")

    def embed_query(self, text: str) -> list[float]:
        return self._embed([text], mode="query")[0]
