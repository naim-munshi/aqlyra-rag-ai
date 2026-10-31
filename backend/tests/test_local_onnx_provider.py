"""Use actual local E5 metadata; never generate fake semantic embeddings."""
import math

import pytest

from app.embeddings.registry import create_embedding_provider
from app.embeddings.local_onnx_provider import LocalMultilingualE5Provider
from app.embeddings.types import EmbeddingProviderRequestError, EmbeddingValidationError


class Encoder:
    def __init__(self):
        self.calls = []
    def encode(self, texts, *, mode):
        self.calls.append((list(texts), mode))
        return [[0.0, 3.0, 4.0] + [0.0] * 381 for _ in texts]


def test_local_e5_normalized_real_vectors_and_query_passage_modes():
    encoder = Encoder()
    p = LocalMultilingualE5Provider(client=encoder, max_batch_size=4)
    assert p.info.dimension == 384
    assert p.info.provider_name == "local_onnx"
    docs = p.embed_documents(["বাংলা লেখা", "日本語の文章"])
    q = p.embed_query("What is this about?")
    assert [mode for _, mode in encoder.calls] == ["passage", "query"]
    assert len(docs) == 2 and len(q) == 384
    assert math.isclose(math.sqrt(sum(v*v for v in q)), 1.0)
    assert docs[0][1:3] == pytest.approx([0.6, 0.8])
    assert p.info.model_name == "multilingual-e5-small-int8-v1"


def test_local_e5_rejects_incorrect_dimensions():
    with pytest.raises(EmbeddingValidationError):
        LocalMultilingualE5Provider(dimension=768, client=Encoder())


def test_registry_registers_local_semantic_mode():
    e = Encoder()
    p = create_embedding_provider(
        provider_name="local_onnx", dimension=384, max_batch_size=4, client=e,
    )
    assert p.embed_query("こんにちは")[2] == pytest.approx(0.8)


def test_does_not_silently_fabricate_vectors_on_inference_outage():
    class Failure:
        def encode(self, texts, *, mode):
            raise RuntimeError("internal model failure with sensitive text")
    p = LocalMultilingualE5Provider(client=Failure())
    with pytest.raises(EmbeddingProviderRequestError, match="Local E5 semantic encoding failed"):
        p.embed_query("User's private note")


def test_local_e5_batch_limit_and_shape_validation():
    p = LocalMultilingualE5Provider(max_batch_size=1, client=Encoder())
    with pytest.raises(EmbeddingValidationError):
        p.embed_documents(["one", "two"])
