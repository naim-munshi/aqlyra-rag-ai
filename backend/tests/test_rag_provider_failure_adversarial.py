import pytest

import app.api.rag as rag_api
import app.services.rag_answer_service as rag_service
from app.llms import (
    LLMGeneration,
    LLMProviderInfo,
    LLMProviderRequestError,
    LLMProviderResponseError,
)
from app.rag import (
    EvidenceContext,
    EvidenceSource,
)
from app.rag.grounding_verifier import (
    GroundingVerificationResult,
    GroundingVerifierRequestError,
    GroundingVerifierResponseError,
    LLMGroundingVerifier,
)


PASSWORD = "ProviderFailurePass123!"


class StaticGenerationProvider:
    def __init__(self) -> None:
        self._info = LLMProviderInfo(
            provider_name="generation-test",
            model_name="generation-test-v1",
            max_output_tokens=500,
        )

        self.calls = 0

    @property
    def info(self) -> LLMProviderInfo:
        return self._info

    def generate(
        self,
        *,
        instructions: str,
        input_text: str,
    ) -> LLMGeneration:
        self.calls += 1

        return LLMGeneration(
            text=(
                "JWT bearer tokens protect "
                "private API routes [S1]."
            ),
            provider_name=(
                self.info.provider_name
            ),
            model_name=self.info.model_name,
            response_id=(
                f"generation-{self.calls}"
            ),
            input_tokens=100,
            output_tokens=20,
            total_tokens=120,
        )


class RequestFailingProvider(
    StaticGenerationProvider
):
    def generate(
        self,
        *,
        instructions: str,
        input_text: str,
    ) -> LLMGeneration:
        raise LLMProviderRequestError(
            "429 rate limit / timeout"
        )


class ResponseFailingProvider(
    StaticGenerationProvider
):
    def generate(
        self,
        *,
        instructions: str,
        input_text: str,
    ) -> LLMGeneration:
        raise LLMProviderResponseError(
            "malformed provider response"
        )


class RequestFailingVerifier:
    def verify(
        self,
        *,
        answer,
    ):
        raise GroundingVerifierRequestError(
            "429 rate limit / timeout"
        )


class ResponseFailingVerifier:
    def verify(
        self,
        *,
        answer,
    ):
        raise GroundingVerifierResponseError(
            "invalid verifier response"
        )


class TransientVerifier:
    def __init__(self) -> None:
        self.calls = 0

    def verify(
        self,
        *,
        answer,
    ) -> GroundingVerificationResult:
        self.calls += 1

        if self.calls == 1:
            raise GroundingVerifierRequestError(
                "temporary verifier outage"
            )

        return GroundingVerificationResult(
            supported=True,
            provider_name="verifier-test",
            model_name="verifier-test-v1",
            response_id="verify-ok",
            input_tokens=20,
            output_tokens=1,
            total_tokens=21,
        )


def evidence_context() -> EvidenceContext:
    source = EvidenceSource(
        source_id="S1",
        chunk_id="chunk-1",
        document_id="document-1",
        original_filename="security.md",
        parent_chunk_id=None,
        chunk_role="content",
        chunk_level=0,
        chunk_index=0,
        source_label="Authentication",
        section_path=(
            "Security",
            "Authentication",
        ),
        start_page=1,
        end_page=1,
        similarity_score=0.99,
        content=(
            "JWT bearer tokens protect "
            "private API routes."
        ),
        was_truncated=False,
    )

    return EvidenceContext(
        text=(
            "[S1] security.md — Authentication\n"
            + source.content
        ),
        sources=(source,),
        estimated_tokens=30,
        skipped_count=0,
        was_truncated=False,
    )


def configure_service(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        rag_service,
        "_retrieve_rag_hits",
        lambda **kwargs: [],
    )

    monkeypatch.setattr(
        rag_service,
        "build_evidence_context",
        lambda *args, **kwargs: (
            evidence_context()
        ),
    )


def create_auth_headers(
    client,
    *,
    suffix: str,
) -> dict[str, str]:
    register = client.post(
        "/api/v1/auth/register",
        json={
            "username": suffix,
            "email": f"{suffix}@example.com",
            "password": PASSWORD,
        },
    )

    assert register.status_code == 201

    login = client.post(
        "/api/v1/auth/login",
        json={
            "email": f"{suffix}@example.com",
            "password": PASSWORD,
        },
    )

    assert login.status_code == 200

    return {
        "Authorization": (
            "Bearer "
            + login.json()["access_token"]
        )
    }


def test_verifier_request_error_is_llm_request_error(
) -> None:
    assert issubclass(
        GroundingVerifierRequestError,
        LLMProviderRequestError,
    )


def test_verifier_response_error_is_llm_response_error(
) -> None:
    assert issubclass(
        GroundingVerifierResponseError,
        LLMProviderResponseError,
    )


def test_llm_verifier_preserves_request_failure_class(
) -> None:
    verifier = LLMGroundingVerifier(
        provider=RequestFailingProvider()
    )

    provider = StaticGenerationProvider()

    configure_source = evidence_context()

    from app.rag import (
        GroundedAnswerDraft,
        validate_grounded_answer_draft,
    )

    draft = GroundedAnswerDraft(
        question="How are routes protected?",
        answer_text=(
            "JWT bearer tokens protect "
            "private API routes [S1]."
        ),
        sources=configure_source.sources,
        provider_name=provider.info.provider_name,
        model_name=provider.info.model_name,
        response_id="draft-1",
        input_tokens=100,
        output_tokens=20,
        total_tokens=120,
        evidence_tokens=30,
        skipped_evidence_count=0,
        evidence_was_truncated=False,
    )

    validated = validate_grounded_answer_draft(
        draft
    )

    with pytest.raises(
        GroundingVerifierRequestError
    ):
        verifier.verify(
            answer=validated
        )


def test_llm_verifier_preserves_response_failure_class(
) -> None:
    verifier = LLMGroundingVerifier(
        provider=ResponseFailingProvider()
    )

    context = evidence_context()

    from app.rag import (
        GroundedAnswerDraft,
        validate_grounded_answer_draft,
    )

    draft = GroundedAnswerDraft(
        question="How are routes protected?",
        answer_text=(
            "JWT bearer tokens protect "
            "private API routes [S1]."
        ),
        sources=context.sources,
        provider_name="generation-test",
        model_name="generation-test-v1",
        response_id="draft-2",
        input_tokens=100,
        output_tokens=20,
        total_tokens=120,
        evidence_tokens=30,
        skipped_evidence_count=0,
        evidence_was_truncated=False,
    )

    validated = validate_grounded_answer_draft(
        draft
    )

    with pytest.raises(
        GroundingVerifierResponseError
    ):
        verifier.verify(
            answer=validated
        )


def test_service_propagates_verifier_429_or_timeout(
    monkeypatch,
) -> None:
    configure_service(monkeypatch)

    provider = StaticGenerationProvider()

    with pytest.raises(
        GroundingVerifierRequestError
    ):
        rag_service.answer_question(
            db=None,
            user_id="provider-failure-user",
            question=(
                "How are private routes protected?"
            ),
            provider=provider,
            grounding_verifier=(
                RequestFailingVerifier()
            ),
        )

    assert provider.calls == 1


def test_service_propagates_verifier_bad_response(
    monkeypatch,
) -> None:
    configure_service(monkeypatch)

    provider = StaticGenerationProvider()

    with pytest.raises(
        GroundingVerifierResponseError
    ):
        rag_service.answer_question(
            db=None,
            user_id="provider-response-user",
            question=(
                "How are private routes protected?"
            ),
            provider=provider,
            grounding_verifier=(
                ResponseFailingVerifier()
            ),
        )

    assert provider.calls == 1


def test_transient_verifier_failure_recovers_on_next_request(
    monkeypatch,
) -> None:
    configure_service(monkeypatch)

    provider = StaticGenerationProvider()
    verifier = TransientVerifier()

    with pytest.raises(
        GroundingVerifierRequestError
    ):
        rag_service.answer_question(
            db=None,
            user_id="transient-user",
            question=(
                "How are private routes protected?"
            ),
            provider=provider,
            grounding_verifier=verifier,
        )

    result = rag_service.answer_question(
        db=None,
        user_id="transient-user",
        question=(
            "How are private routes protected?"
        ),
        provider=provider,
        grounding_verifier=verifier,
    )

    assert result.is_refusal is False
    assert result.citation_count == 1
    assert verifier.calls == 2
    assert provider.calls == 2


def test_rag_api_maps_verifier_request_failure_to_503(
    client,
    monkeypatch,
) -> None:
    headers = create_auth_headers(
        client,
        suffix="verifier-request-api",
    )

    def fail_answer(**kwargs):
        raise GroundingVerifierRequestError(
            "429 quota exceeded"
        )

    monkeypatch.setattr(
        rag_api,
        "answer_question",
        fail_answer,
    )

    response = client.post(
        "/api/v1/rag/answer",
        headers=headers,
        json={
            "question": "Test provider outage",
        },
    )

    assert response.status_code == 503

    assert response.json()["detail"] == (
        "RAG provider service is unavailable"
    )


def test_rag_api_maps_verifier_response_failure_to_502(
    client,
    monkeypatch,
) -> None:
    headers = create_auth_headers(
        client,
        suffix="verifier-response-api",
    )

    def fail_answer(**kwargs):
        raise GroundingVerifierResponseError(
            "invalid verifier response"
        )

    monkeypatch.setattr(
        rag_api,
        "answer_question",
        fail_answer,
    )

    response = client.post(
        "/api/v1/rag/answer",
        headers=headers,
        json={
            "question": "Test bad response",
        },
    )

    assert response.status_code == 502

    assert response.json()["detail"] == (
        "The generated answer failed "
        "grounding validation"
    )
