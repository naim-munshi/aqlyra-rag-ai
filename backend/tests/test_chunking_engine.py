from app.chunking import (
    ChunkingConfig,
    ChunkSource,
    build_chunks,
)


def create_source(
    content: str,
) -> ChunkSource:
    return ChunkSource(
        document_id="document-1",
        document_label="research.md",
        unit_id="unit-1",
        unit_index=1,
        unit_type="section",
        source_label="Introduction",
        content=content,
        metadata={
            "heading": "Introduction",
            "heading_level": 1,
        },
    )


def test_short_unit_creates_single_content_chunk() -> None:
    source = create_source(
        "Ihsan RAG AI retrieves evidence "
        "and produces cited answers."
    )

    chunks = build_chunks([source])

    assert len(chunks) == 1

    chunk = chunks[0]

    assert chunk.chunk_role == "content"
    assert chunk.chunk_level == 0
    assert chunk.parent_chunk_id is None
    assert chunk.section_path == (
        "Introduction",
    )
    assert chunk.content == source.content
    assert chunk.start_char == 0
    assert chunk.end_char == len(
        source.content
    )
    assert "Document: research.md" in (
        chunk.embedding_content
    )
    assert "Section: Introduction" in (
        chunk.embedding_content
    )


def test_long_unit_creates_parent_and_children() -> None:
    content = " ".join(
        (
            f"Sentence {number} explains "
            "retrieval augmented generation "
            "with reliable source citations."
        )
        for number in range(1, 31)
    )

    source = create_source(content)

    config = ChunkingConfig(
        default_target_tokens=40,
        min_chunk_tokens=15,
        max_chunk_tokens=55,
        overlap_tokens=8,
        parent_summary_tokens=20,
    )

    chunks = build_chunks(
        [source],
        config=config,
    )

    parent_chunks = [
        chunk
        for chunk in chunks
        if chunk.chunk_role == "summary"
    ]

    child_chunks = [
        chunk
        for chunk in chunks
        if chunk.chunk_role == "content"
    ]

    assert len(parent_chunks) == 1
    assert len(child_chunks) > 1

    parent = parent_chunks[0]

    assert parent.chunk_level == 1
    assert parent.parent_chunk_id is None

    assert all(
        child.parent_chunk_id
        == parent.id
        for child in child_chunks
    )

    assert all(
        child.chunk_level == 0
        for child in child_chunks
    )


def test_chunk_offsets_match_source_content() -> None:
    content = " ".join(
        (
            f"Section sentence {number} "
            "contains structured evidence."
        )
        for number in range(1, 25)
    )

    source = create_source(content)

    config = ChunkingConfig(
        default_target_tokens=35,
        min_chunk_tokens=12,
        max_chunk_tokens=50,
        overlap_tokens=6,
        parent_summary_tokens=18,
    )

    chunks = build_chunks(
        [source],
        config=config,
    )

    content_chunks = [
        chunk
        for chunk in chunks
        if chunk.chunk_role == "content"
    ]

    for chunk in content_chunks:
        assert chunk.start_char is not None
        assert chunk.end_char is not None

        extracted = content[
            chunk.start_char:
            chunk.end_char
        ].strip()

        assert chunk.content == extracted
        assert chunk.char_count == len(
            chunk.content
        )
        assert chunk.token_count > 0
        assert chunk.content_hash


def test_chunk_generation_is_deterministic() -> None:
    content = " ".join(
        (
            f"Deterministic sentence {number} "
            "describes a stable chunk."
        )
        for number in range(1, 20)
    )

    source = create_source(content)

    config = ChunkingConfig(
        default_target_tokens=40,
        min_chunk_tokens=15,
        max_chunk_tokens=55,
        overlap_tokens=8,
        parent_summary_tokens=20,
    )

    first_result = build_chunks(
        [source],
        config=config,
    )

    second_result = build_chunks(
        [source],
        config=config,
    )

    assert [
        chunk.id
        for chunk in first_result
    ] == [
        chunk.id
        for chunk in second_result
    ]

    assert [
        chunk.content_hash
        for chunk in first_result
    ] == [
        chunk.content_hash
        for chunk in second_result
    ]

    assert [
        chunk.chunk_index
        for chunk in first_result
    ] == [
        chunk.chunk_index
        for chunk in second_result
    ]
