"""One-shot real Knowledge provider smoke; synthetic strings, no user files."""
from app.config.settings import settings
from app.embeddings import create_configured_embedding_provider
from app.llms import create_configured_llm_provider


def run_knowledge_probe() -> None:
    # The deterministic SHA-256 encoder is not semantic. If selected,
    # explicitly verify that the RAG lexical fallback is available.
    if settings.EMBEDDING_PROVIDER == "deterministic":
        if not settings.KNOWLEDGE_LEXICAL_FALLBACK_ENABLED:
            raise RuntimeError("No real embedding provider and lexical mode is disabled")
        print("KNOWLEDGE_RETRIEVAL_PROBE=LEXICAL_ONLY", flush=True)
    else:
        embedder = create_configured_embedding_provider()
        vectors = embedder.embed_documents([
            "Aqlyra synthetic retrieval canary one",
            "Aqlyra synthetic retrieval canary two",
        ])
        if len(vectors) != 2 or any(len(v) != 384 for v in vectors):
            raise RuntimeError("Embedding provider returned inconsistent vectors")
        print("KNOWLEDGE_EMBEDDING_PROBE=PASS", flush=True)

    if settings.LLM_PROVIDER == "deterministic":
        raise RuntimeError("Knowledge generation is using a deterministic test provider")
    llm = create_configured_llm_provider()
    generation = llm.generate(
        instructions="Answer in exactly one short sentence. No source is supplied.",
        input_text="Reply with the words 'Synthetic knowledge canary'.",
    )
    if not generation.text.strip():
        raise RuntimeError("Knowledge LLM returned no answer")
    print("KNOWLEDGE_LLM_PROBE=PASS", flush=True)


if __name__ == "__main__":
    try:
        run_knowledge_probe()
        print("KNOWLEDGE_PROVIDER_PROBE=PASS", flush=True)
    except Exception as exc:
        # Only class; never output auth, user prompts or provider response.
        print(f"KNOWLEDGE_PROVIDER_DIAG={type(exc).__name__}", flush=True)
        print("KNOWLEDGE_PROVIDER_PROBE=FAIL", flush=True)
        raise SystemExit(1)
