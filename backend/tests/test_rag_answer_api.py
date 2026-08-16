from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

import app.api.rag as rag_api_module
import app.services.rag_answer_service as rag_answer_service_module
from app.llms import (
    LLMGeneration,
    LLMProviderInfo,
    LLMProviderRequestError,
)
from app.models.document_chunk import (
    DocumentChunk,
)
from app.rag import MissingCitationError


def create_user(
    client: TestClient,
    *,
    username: str,
    email: str,
) -> tuple[str, dict[str, str]]:
    password = "TestPass123!"

    register_response = client.post(
        "/api/v1/auth/register",
        json={
            "username": username,
            "email": email,
            "password": password,
        },
    )

    assert (
        register_response.status_code
        == 201
    )

    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "email": email,
            "password": password,
        },
    )

    assert login_response.status_code == 200

    token = login_response.json()[
        "access_token"
    ]

    headers = {
        "Authorization": f"Bearer {token}",
    }

    profile_response = client.get(
        "/api/v1/users/me",
        headers=headers,
    )

    assert (
        profile_response.status_code
        == 200
    )

    user_id = profile_response.json()["id"]

    return user_id, headers


def upload_and_process(
    client: TestClient,
    *,
    headers: dict[str, str],
    filename: str,
    content: str,
) -> str:
    upload_response = client.post(
        "/api/v1/documents/upload",
        headers=headers,
        files={
            "file": (
                filename,
                content.encode("utf-8"),
                "text/markdown",
            ),
        },
    )

    assert (
        upload_response.status_code
        == 201
    )

    document_id = upload_response.json()[
        "id"
    ]

    process_response = client.post(
        (
            "/api/v1/documents/"
            f"{document_id}/process"
        ),
        headers=headers,
    )

    assert (
        process_response.status_code
        == 200
    )

    return document_id


def get_content_chunk(
    db_session: Session,
    *,
    document_id: str,
) -> DocumentChunk:
    statement = (
        select(DocumentChunk)
        .where(
            DocumentChunk.document_id
            == document_id,
            DocumentChunk.chunk_role
            == "content",
        )
        .order_by(
            DocumentChunk.chunk_index.asc()
        )
    )

    chunk = db_session.scalar(
        statement
    )

    assert chunk is not None

    return chunk


def test_rag_answer_requires_authentication(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/v1/rag/answer",
        json={
            "question": (
                "How is the API protected?"
            ),
        },
    )

    assert response.status_code == 401


def test_rag_answer_returns_validated_citations(
    client: TestClient,
    db_session: Session,
) -> None:
    _, headers = create_user(
        client,
        username="raguser",
        email="raguser@example.com",
    )

    document_id = upload_and_process(
        client,
        headers=headers,
        filename="security.md",
        content=(
            "# Authentication\n\n"
            "JWT bearer tokens protect "
            "private API routes."
        ),
    )

    chunk = get_content_chunk(
        db_session,
        document_id=document_id,
    )

    response = client.post(
        "/api/v1/rag/answer",
        headers=headers,
        json={
            "question": (
                chunk.embedding_content
            ),
            "top_k": 3,
            "document_ids": [
                document_id,
            ],
            "chunk_roles": [
                "content",
            ],
            "min_similarity": 0.999,
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["is_refusal"] is False

    assert payload["answer"] == (
        "Deterministic grounded "
        "answer [S1]."
    )

    assert payload["provider_name"] == (
        "deterministic"
    )

    assert payload["model_name"] == (
        "deterministic-rag-v1"
    )

    assert payload["citation_count"] == 1
    assert len(payload["citations"]) == 1

    citation = payload["citations"][0]

    assert citation["source_id"] == "S1"

    assert citation["document_id"] == (
        document_id
    )

    assert citation["chunk_id"] == chunk.id

    assert citation["filename"] == (
        "security.md"
    )

    assert (
        citation["similarity_score"]
        >= 0.999
    )

    assert payload["retrieved_count"] >= 1
    assert (
        payload["context_source_count"]
        >= 1
    )

    assert (
        payload["usage"][
            "evidence_tokens"
        ]
        > 0
    )


def test_rag_answer_enforces_user_isolation(
    client: TestClient,
    db_session: Session,
) -> None:
    _, first_headers = create_user(
        client,
        username="firstraguser",
        email="firstrag@example.com",
    )

    _, second_headers = create_user(
        client,
        username="secondraguser",
        email="secondrag@example.com",
    )

    first_document_id = upload_and_process(
        client,
        headers=first_headers,
        filename="first-private.md",
        content=(
            "# First User\n\n"
            "This evidence belongs only "
            "to the first user."
        ),
    )

    second_document_id = upload_and_process(
        client,
        headers=second_headers,
        filename="second-private.md",
        content=(
            "# Second User\n\n"
            "This evidence belongs only "
            "to the second user."
        ),
    )

    second_chunk = get_content_chunk(
        db_session,
        document_id=second_document_id,
    )

    response = client.post(
        "/api/v1/rag/answer",
        headers=first_headers,
        json={
            "question": (
                second_chunk
                .embedding_content
            ),
            "document_ids": [
                second_document_id,
            ],
            "top_k": 5,
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["is_refusal"] is True

    assert payload["citations"] == []
    assert payload["citation_count"] == 0
    assert payload["retrieved_count"] == 0

    assert first_document_id != (
        second_document_id
    )


def test_rag_answer_request_validation(
    client: TestClient,
) -> None:
    _, headers = create_user(
        client,
        username="ragvalidation",
        email=(
            "ragvalidation@example.com"
        ),
    )

    empty_question = client.post(
        "/api/v1/rag/answer",
        headers=headers,
        json={
            "question": "   ",
        },
    )

    assert empty_question.status_code == 422

    invalid_top_k = client.post(
        "/api/v1/rag/answer",
        headers=headers,
        json={
            "question": "Valid question",
            "top_k": 51,
        },
    )

    assert invalid_top_k.status_code == 422

    duplicate_documents = client.post(
        "/api/v1/rag/answer",
        headers=headers,
        json={
            "question": "Valid question",
            "document_ids": [
                "document-1",
                "document-1",
            ],
        },
    )

    assert (
        duplicate_documents.status_code
        == 422
    )

    invalid_budget = client.post(
        "/api/v1/rag/answer",
        headers=headers,
        json={
            "question": "Valid question",
            "max_context_tokens": 500,
            "max_source_tokens": 700,
        },
    )

    assert invalid_budget.status_code == 422


def test_rag_answer_maps_provider_outage(
    client: TestClient,
    monkeypatch,
) -> None:
    _, headers = create_user(
        client,
        username="ragoutage",
        email="ragoutage@example.com",
    )

    def raise_provider_error(
        **kwargs,
    ):
        raise LLMProviderRequestError(
            "Provider unavailable"
        )

    monkeypatch.setattr(
        rag_api_module,
        "answer_question",
        raise_provider_error,
    )

    response = client.post(
        "/api/v1/rag/answer",
        headers=headers,
        json={
            "question": "Valid question",
        },
    )

    assert response.status_code == 503

    assert response.json()["detail"] == (
        "RAG provider service "
        "is unavailable"
    )


def test_rag_answer_maps_citation_failure(
    client: TestClient,
    monkeypatch,
) -> None:
    _, headers = create_user(
        client,
        username="ragcitation",
        email=(
            "ragcitation@example.com"
        ),
    )

    def raise_citation_error(
        **kwargs,
    ):
        raise MissingCitationError(
            "Answer contains no citations"
        )

    monkeypatch.setattr(
        rag_api_module,
        "answer_question",
        raise_citation_error,
    )

    response = client.post(
        "/api/v1/rag/answer",
        headers=headers,
        json={
            "question": "Valid question",
        },
    )

    assert response.status_code == 502

    assert response.json()["detail"] == (
        "The generated answer failed "
        "grounding validation"
    )


class SequencedRAGLLMProvider:
    def __init__(
        self,
        response_texts: tuple[str, ...],
    ) -> None:
        if not response_texts:
            raise ValueError(
                "At least one response is required"
            )

        self._response_texts = response_texts

        self._info = LLMProviderInfo(
            provider_name="sequenced-test",
            model_name="sequenced-test-v1",
            max_output_tokens=500,
        )

        self.calls: list[
            tuple[str, str]
        ] = []

    @property
    def info(self) -> LLMProviderInfo:
        return self._info

    def generate(
        self,
        *,
        instructions: str,
        input_text: str,
    ) -> LLMGeneration:
        self.calls.append(
            (
                instructions,
                input_text,
            )
        )

        index = min(
            len(self.calls) - 1,
            len(self._response_texts) - 1,
        )

        return LLMGeneration(
            text=self._response_texts[index],
            provider_name=(
                self.info.provider_name
            ),
            model_name=self.info.model_name,
            response_id=(
                f"sequenced-{len(self.calls)}"
            ),
            input_tokens=100,
            output_tokens=20,
            total_tokens=120,
        )


def test_rag_answer_uses_second_repair_when_needed(
    client: TestClient,
    db_session: Session,
    monkeypatch,
) -> None:
    _, headers = create_user(
        client,
        username="ragsecondrepair",
        email="ragsecondrepair@example.com",
    )

    document_id = upload_and_process(
        client,
        headers=headers,
        filename="repair-security.md",
        content=(
            "# Authentication\n\n"
            "JWT bearer tokens protect "
            "private API routes."
        ),
    )

    chunk = get_content_chunk(
        db_session,
        document_id=document_id,
    )

    provider = SequencedRAGLLMProvider(
        (
            (
                "JWT bearer tokens protect "
                "private API routes."
            ),
            (
                "JWT bearer tokens protect "
                "private API routes."
            ),
            (
                "JWT bearer tokens protect "
                "private API routes [S1]."
            ),
        )
    )

    monkeypatch.setattr(
        rag_answer_service_module,
        "create_configured_llm_provider",
        lambda: provider,
    )

    response = client.post(
        "/api/v1/rag/answer",
        headers=headers,
        json={
            "question":
                chunk.embedding_content,
            "top_k": 3,
            "document_ids": [
                document_id,
            ],
            "chunk_roles": [
                "content",
            ],
            "min_similarity": 0.999,
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["is_refusal"] is False

    assert (
        "[S1]"
        in payload["answer"]
    )

    assert payload["citation_count"] == 1

    assert len(
        payload["citations"]
    ) == 1

    assert len(provider.calls) == 3


def test_rag_answer_safely_refuses_after_two_invalid_repairs(
    client: TestClient,
    db_session: Session,
    monkeypatch,
) -> None:
    _, headers = create_user(
        client,
        username="ragsafefallback",
        email="ragsafefallback@example.com",
    )

    document_id = upload_and_process(
        client,
        headers=headers,
        filename="fallback-security.md",
        content=(
            "# Authentication\n\n"
            "JWT bearer tokens protect "
            "private API routes."
        ),
    )

    chunk = get_content_chunk(
        db_session,
        document_id=document_id,
    )

    invalid_answer = (
        "JWT bearer tokens protect "
        "private API routes."
    )

    provider = SequencedRAGLLMProvider(
        (
            invalid_answer,
            invalid_answer,
            invalid_answer,
        )
    )

    monkeypatch.setattr(
        rag_answer_service_module,
        "create_configured_llm_provider",
        lambda: provider,
    )

    response = client.post(
        "/api/v1/rag/answer",
        headers=headers,
        json={
            "question":
                chunk.embedding_content,
            "top_k": 3,
            "document_ids": [
                document_id,
            ],
            "chunk_roles": [
                "content",
            ],
            "min_similarity": 0.999,
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["is_refusal"] is True
    assert payload["citations"] == []
    assert payload["citation_count"] == 0

    assert len(provider.calls) == 3
