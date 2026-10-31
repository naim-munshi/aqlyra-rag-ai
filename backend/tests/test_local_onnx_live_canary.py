"""One-shot real model / cross-language semantic embedding acceptance."""
from math import isclose
from app.embeddings.local_onnx_provider import LocalMultilingualE5Provider


def test_real_multilingual_e5_semantic_retrieval():
    p = LocalMultilingualE5Provider(max_batch_size=4)
    texts = [
        "Japan's capital city is Tokyo.",
        "A chocolate cake recipe requires flour.",
        "日本の首都は東京です。",
    ]
    docs = p.embed_documents(texts)
    queries = [p.embed_query("What city is the capital of Japan?"),
               p.embed_query("日本の首都について教えてください。")]
    assert len(docs) == 3 and all(len(v) == 384 for v in docs)
    assert all(isclose(sum(v * v for v in vector), 1.0, abs_tol=0.002)
               for vector in docs + queries)
    def dot(a, b):
        return sum(x * y for x, y in zip(a, b))
    assert dot(queries[0], docs[0]) > dot(queries[0], docs[1])
    assert dot(queries[1], docs[2]) > dot(queries[1], docs[1])
