import json

from scripts import (
    build_retrieval_corpus as corpus,
)


def test_controlled_corpus_has_unique_cases(
    tmp_path,
    monkeypatch,
) -> None:
    corpus_dir = (
        tmp_path
        / "corpus"
    )

    dataset_path = (
        tmp_path
        / "retrieval_cases.json"
    )

    monkeypatch.setattr(
        corpus,
        "CORPUS_DIR",
        corpus_dir,
    )

    monkeypatch.setattr(
        corpus,
        "DATASET_PATH",
        dataset_path,
    )

    corpus.main()

    files = sorted(
        corpus_dir.glob("*.md")
    )

    assert len(files) == 10

    payload = json.loads(
        dataset_path.read_text(
            encoding="utf-8"
        )
    )

    cases = payload["cases"]

    assert len(cases) == 20

    query_ids = {
        case["query_id"]
        for case in cases
    }

    assert len(query_ids) == 20

    for case in cases:
        document_path = (
            corpus_dir
            / case["document_filename"]
        )

        assert document_path.exists()

        content = (
            document_path
            .read_text(
                encoding="utf-8"
            )
        )

        assert (
            case["evidence_marker"]
            in content
        )
