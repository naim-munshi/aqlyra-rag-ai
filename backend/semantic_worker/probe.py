"""Real multilingual semantic acceptance probe; public synthetic texts only."""
import os
import resource
from semantic_worker.model import get_encoder, DIMENSION


def main():
    encoder = get_encoder()
    samples = [
        "Tokyo is the capital of Japan.",
        "Chocolate cake requires flour.",
        "日本の首都は東京です。",
    ]
    docs = encoder.encode(samples, "passage")
    en = encoder.encode(["What is Japan's capital?"], "query")[0]
    ja = encoder.encode(["日本の首都はどこですか？"], "query")[0]
    assert len(docs) == 3 and len(en) == DIMENSION and len(ja) == DIMENSION
    def dot(a,b):
        return sum(x*y for x,y in zip(a,b))
    assert dot(en, docs[0]) > dot(en, docs[1])
    assert dot(ja, docs[2]) > dot(ja, docs[1])
    print("ISOLATED_SEMANTIC_PROBE=PASS dimension=384 languages=en,ja", flush=True)
    print("ISOLATED_SEMANTIC_PEAK_RSS_KB=" + str(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss), flush=True)


if __name__ == "__main__":
    main()
