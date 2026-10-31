"""One-shot public model smoke; does not use any user documents."""
from math import isclose
from .local_onnx_provider import LocalMultilingualE5Provider


def main() -> None:
    provider = LocalMultilingualE5Provider(max_batch_size=4)
    docs = provider.embed_documents([
        "Tokyo is the capital of Japan.",
        "Chocolate cake requires flour and eggs.",
        "日本の首都は東京です。",
    ])
    en = provider.embed_query("What is Japan's capital?")
    ja = provider.embed_query("日本の首都はどこですか？")
    def dot(a, b):
        return sum(x*y for x, y in zip(a, b))
    assert len(docs) == 3 and len(en) == 384 and len(ja) == 384
    assert all(isclose(sum(v*v for v in z), 1.0, abs_tol=0.002)
               for z in docs + [en, ja])
    assert dot(en, docs[0]) > dot(en, docs[1])
    assert dot(ja, docs[2]) > dot(ja, docs[1])
    print("LOCAL_SEMANTIC_ONNX_PROBE=PASS dimensionality=384 languages=en,ja")


if __name__ == "__main__":
    main()
