"""Optional CPU-local multilingual semantic embeddings, no inference API key.

Model: Xenova/multilingual-e5-small, quantized INT8 ONNX (~118 MB),
384 dimensions, with E5 query/passage prefixes and mean pooling.
Downloaded lazily from the public model repo; no user text is sent to HF.
Never silently substitute synthetic hashes for actual semantic vectors.
"""
from __future__ import annotations

from collections.abc import Sequence
from threading import Lock
from typing import Any

from app.embeddings.types import (
    EmbeddingProviderInfo,
    EmbeddingProviderRequestError,
    EmbeddingValidationError,
)
from app.embeddings.validation import (
    normalize_vector, validate_embedding_vector, validate_text_batch,
)

_MODEL_REPO = "Xenova/multilingual-e5-small"
_MODEL_FILE = "onnx/model_quantized.onnx"
_MODEL_NAME = "multilingual-e5-small-int8-v1"
_MODEL_DIM = 384
_DEFAULT_BATCH = 8
_ENCODER_LOCK = Lock()
_SHARED_ENCODER: Any | None = None


class _LocalE5Encoder:
    def __init__(self) -> None:
        # Lazy imports keep staging, deterministic tests and current HF
        # provider independent of optional ONNX packages / model downloads.
        import numpy as np
        import onnxruntime as ort
        from huggingface_hub import hf_hub_download
        from tokenizers import Tokenizer

        model_path = hf_hub_download(
            repo_id=_MODEL_REPO, filename=_MODEL_FILE,
        )
        tokenizer_path = hf_hub_download(
            repo_id=_MODEL_REPO, filename="tokenizer.json",
        )
        self._np = np
        self._tokenizer = Tokenizer.from_file(tokenizer_path)
        self._tokenizer.enable_truncation(max_length=512)
        pad_id = self._tokenizer.token_to_id("<pad>")
        if pad_id is None:
            raise EmbeddingValidationError("Local E5 tokenizer has no padding token")
        self._tokenizer.enable_padding(pad_id=pad_id, pad_token="<pad>")
        options = ort.SessionOptions()
        options.intra_op_num_threads = 1
        options.inter_op_num_threads = 1
        self._session = ort.InferenceSession(
            str(model_path),
            sess_options=options,
            providers=["CPUExecutionProvider"],
        )
        self._inputs = tuple(item.name for item in self._session.get_inputs())
        if not {"input_ids", "attention_mask"}.issubset(self._inputs):
            raise EmbeddingValidationError("Unexpected E5 ONNX input contract")

    def encode(self, texts: Sequence[str], *, mode: str) -> list[list[float]]:
        np = self._np
        prefix = "query: " if mode == "query" else "passage: "
        tokens = self._tokenizer.encode_batch([prefix + t for t in texts])
        ids = np.asarray([t.ids for t in tokens], dtype=np.int64)
        mask = np.asarray([t.attention_mask for t in tokens], dtype=np.int64)
        feed = {"input_ids": ids, "attention_mask": mask}
        if "token_type_ids" in self._inputs:
            feed["token_type_ids"] = np.zeros_like(ids, dtype=np.int64)
        if any(name not in feed for name in self._inputs):
            raise EmbeddingValidationError("Unsupported E5 ONNX input signature")
        output = self._session.run(None, feed)[0]
        if output.ndim == 3 and output.shape[:2] == mask.shape:
            weights = mask[:, :, None].astype(np.float32)
            output = (output * weights).sum(axis=1) / np.maximum(
                weights.sum(axis=1), 1,
            )
        if output.ndim != 2 or output.shape != (len(texts), _MODEL_DIM):
            raise EmbeddingValidationError("Unexpected E5 ONNX output shape")
        return output.tolist()


class LocalMultilingualE5Provider:
    def __init__(
        self, *, dimension: int = 384,
        max_batch_size: int = _DEFAULT_BATCH,
        client: Any | None = None,
    ) -> None:
        if dimension != _MODEL_DIM:
            raise EmbeddingValidationError("Local E5 requires 384-dimensional vectors")
        if not 1 <= max_batch_size <= 16:
            raise EmbeddingValidationError("Local E5 batch size must be 1..16")
        self._info = EmbeddingProviderInfo(
            provider_name="local_onnx",
            model_name=_MODEL_NAME,
            dimension=dimension,
            max_batch_size=max_batch_size,
        )
        self._encoder = client

    @property
    def info(self) -> EmbeddingProviderInfo:
        return self._info

    def _ensure_encoder(self):
        global _SHARED_ENCODER
        if self._encoder is not None:
            return self._encoder
        # All request-scoped provider objects reuse one bounded model.
        # Avoid costly repeated downloads/initialization after cold start.
        with _ENCODER_LOCK:
            if _SHARED_ENCODER is None:
                try:
                    _SHARED_ENCODER = _LocalE5Encoder()
                except Exception as exc:
                    raise EmbeddingProviderRequestError(
                        "Local E5 model download or initialization failed"
                    ) from exc
            return _SHARED_ENCODER

    def _embed(self, texts: Sequence[str], mode: str) -> list[list[float]]:
        validated = validate_text_batch(
            texts=texts, max_batch_size=self.info.max_batch_size,
        )
        try:
            output = self._ensure_encoder().encode(validated, mode=mode)
        except EmbeddingValidationError:
            raise
        except Exception as exc:
            raise EmbeddingProviderRequestError(
                "Local E5 semantic encoding failed"
            ) from exc
        if len(output) != len(validated):
            raise EmbeddingValidationError("Local E5 returned incorrect batch size")
        result: list[list[float]] = []
        for values in output:
            vector = normalize_vector([float(v) for v in values])
            validate_embedding_vector(
                vector=vector, expected_dimension=self.info.dimension,
            )
            result.append(vector)
        return result

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return self._embed(texts, mode="passage")

    def embed_query(self, text: str) -> list[float]:
        return self._embed([text], mode="query")[0]
