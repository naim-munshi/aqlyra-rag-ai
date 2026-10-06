from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
APP = BACKEND / "app"
RESEARCH = ROOT / "research"


def check_path(path: Path) -> dict:
    return {
        "path": str(path.relative_to(ROOT)),
        "exists": path.exists(),
        "is_file": path.is_file(),
        "is_dir": path.is_dir(),
    }


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def main() -> int:
    print("=" * 72)
    print("AQLYRA CURRENT RAG RESEARCH BASELINE AUDIT")
    print("=" * 72)

    print("\n[1] Repository")
    print(f"Root: {ROOT}")
    print(f"Git branch:")
    subprocess.run(
        ["git", "-C", str(ROOT), "branch", "--show-current"],
        check=False,
    )

    print("\n[2] Required architecture directories")
    required_dirs = [
        APP / "auth",
        APP / "retrieval",
        APP / "rag",
        APP / "llms",
        APP / "embeddings",
        APP / "services",
        BACKEND / "tests",
    ]

    structure = [check_path(p) for p in required_dirs]

    for item in structure:
        status = "OK" if item["exists"] and item["is_dir"] else "MISSING"
        print(f"{status:8} {item['path']}")

    print("\n[3] Effective runtime configuration")
    sys.path.insert(0, str(BACKEND))

    try:
        from app.config.settings import settings
    except Exception as exc:
        print(f"ERROR: Could not load backend settings: {exc}")
        return 1

    config = {
        "llm_provider": settings.LLM_PROVIDER,
        "llm_model": settings.LLM_MODEL,
        "llm_reasoning_effort": settings.LLM_REASONING_EFFORT,
        "llm_max_output_tokens": settings.LLM_MAX_OUTPUT_TOKENS,
        "embedding_provider": settings.EMBEDDING_PROVIDER,
        "embedding_model": settings.EMBEDDING_MODEL,
        "embedding_dimension": settings.EMBEDDING_DIMENSION,
        "rag_reranker_enabled": settings.RAG_RERANKER_ENABLED,
        "reranker_provider": settings.RERANKER_PROVIDER,
        "rag_query_rewrite_enabled": settings.RAG_QUERY_REWRITE_ENABLED,
        "query_rewriter_provider": settings.QUERY_REWRITER_PROVIDER,
        "memory_auto_extract_enabled": settings.MEMORY_AUTO_EXTRACT_ENABLED,
        "memory_chat_enabled": settings.MEMORY_CHAT_ENABLED,
        "secret_presence": {
            "groq_api_key": bool(settings.GROQ_API_KEY.strip()),
            "openai_api_key": bool(settings.OPENAI_API_KEY.strip()),
            "hf_token": bool(settings.HF_TOKEN.strip()),
        },
    }

    print(json.dumps(config, indent=2, ensure_ascii=False))

    print("\n[4] Pipeline documentation checks")

    pipeline_doc = ROOT / "docs" / "RAG_PIPELINE.md"
    architecture_doc = ROOT / "docs" / "ARCHITECTURE.md"

    docs = {}

    if pipeline_doc.exists():
        text = read_text(pipeline_doc)

        expected_phrases = [
            "resolve owned document scope",
            "dense semantic retrieval",
            "lexical full-text retrieval",
            "RRF",
            "build evidence",
            "Validate the returned citations",
            "check whether the cited evidence actually supports",
            "Repair the answer",
            "Refuse the answer",
        ]

        docs["rag_pipeline"] = {
            phrase: phrase.lower() in text.lower()
            for phrase in expected_phrases
        }

    if architecture_doc.exists():
        text = read_text(architecture_doc)

        expected_phrases = [
            "Knowledge request flow",
            "Dense Retrieval",
            "Lexical Retrieval",
            "RRF",
            "Citation Check",
            "Grounding Check",
            "Answer / Repair / Refusal",
        ]

        docs["architecture"] = {
            phrase: phrase.lower() in text.lower()
            for phrase in expected_phrases
        }

    print(json.dumps(docs, indent=2, ensure_ascii=False))

    print("\n[5] Relevant test inventory")

    test_files = sorted(BACKEND.glob("tests/test_*.py"))

    patterns = [
        "retriev",
        "rrf",
        "citation",
        "ground",
        "scope",
        "ownership",
        "cross_user",
        "document",
        "rag",
        "embedding",
    ]

    matched_files: set[str] = set()

    for file in test_files:
        name = file.name.lower()
        content = read_text(file).lower()

        if any(
            pattern in name or pattern in content
            for pattern in patterns
        ):
            matched_files.add(str(file.relative_to(ROOT)))

    print(f"Total test modules discovered: {len(test_files)}")
    print(f"Relevant test modules discovered: {len(matched_files)}")

    for file in sorted(matched_files):
        print(f"  {file}")

    print("\n[6] Source-level safety/order signals")

    source_files = list(APP.rglob("*.py"))

    signals = {
        "document_scope": [],
        "dense_retrieval": [],
        "lexical_retrieval": [],
        "rrf": [],
        "citation": [],
        "grounding": [],
        "repair": [],
        "refusal": [],
    }

    regexes = {
        "document_scope": re.compile(
            r"(document.?scope|owned.?document|scope_ids?|ownership)",
            re.I,
        ),
        "dense_retrieval": re.compile(
            r"dense.?retriev|vector.?search|pgvector",
            re.I,
        ),
        "lexical_retrieval": re.compile(
            r"lexical.?retriev|full.?text|tsquery|tsvector",
            re.I,
        ),
        "rrf": re.compile(r"\bRRF\b|reciprocal.?rank", re.I),
        "citation": re.compile(r"citation", re.I),
        "grounding": re.compile(r"ground", re.I),
        "repair": re.compile(r"\brepair\b", re.I),
        "refusal": re.compile(r"\brefus(e|al)\b|\babstain", re.I),
    }

    for file in source_files:
        text = read_text(file)

        for key, pattern in regexes.items():
            if pattern.search(text):
                signals[key].append(str(file.relative_to(ROOT)))

    for key, files in signals.items():
        print(f"\n{key}: {len(files)} files")
        for file in files[:20]:
            print(f"  {file}")

        if len(files) > 20:
            print(f"  ... +{len(files) - 20} more")

    print("\n[7] Research baseline interpretation")

    warnings = []

    if settings.EMBEDDING_PROVIDER == "deterministic":
        warnings.append(
            "DETERMINISTIC EMBEDDING ACTIVE: retrieval results should NOT "
            "be treated as semantic-retrieval research results."
        )

    if settings.LLM_PROVIDER == "deterministic":
        warnings.append(
            "DETERMINISTIC LLM ACTIVE: this is appropriate for structural "
            "tests, but not for final generation-quality experiments."
        )

    if settings.RAG_RERANKER_ENABLED:
        print("Reranker: ENABLED")
    else:
        print("Reranker: DISABLED")

    if settings.RAG_QUERY_REWRITE_ENABLED:
        print("Query rewriting: ENABLED")
    else:
        print("Query rewriting: DISABLED")

    if warnings:
        print("\nWARNINGS:")
        for warning in warnings:
            print(f"  - {warning}")
    else:
        print("No baseline configuration warnings detected.")

    output = {
        "repository_root": str(ROOT),
        "configuration": config,
        "structure": structure,
        "documentation_signals": docs,
        "test_module_count": len(test_files),
        "relevant_test_modules": sorted(matched_files),
        "source_signals": signals,
        "warnings": warnings,
    }

    output_path = RESEARCH / "current_rag_baseline_audit.json"
    output_path.write_text(
        json.dumps(output, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"\nAudit report written to:")
    print(output_path.relative_to(ROOT))

    print("\nAUDIT COMPLETE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
