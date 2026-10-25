"""Authenticated live public web research. Never reads private documents."""
from fastapi import APIRouter, Depends, HTTPException
from app.api.dependencies import get_current_user
from app.core.rate_limit import limit_rag_request
from app.llms import LLMError
from app.models.user import User
from app.schemas.web_research import WebResearchRequest, WebResearchResponse
from app.services.web_research_service import (
    WebResearchUnavailable, WebResearchEvidenceError, research_web,
)

router = APIRouter(prefix="/web", tags=["Web Research"])


@router.post(
    "/research",
    response_model=WebResearchResponse,
    dependencies=[Depends(limit_rag_request)],
)
def research_public_web(
    body: WebResearchRequest,
    current_user: User = Depends(get_current_user),
) -> WebResearchResponse:
    del current_user
    try:
        return research_web(
            body.question, body.max_sources,
            mode=body.mode, source_url=body.source_url,
        )
    except WebResearchUnavailable as exc:
        raise HTTPException(
            status_code=503, detail="Web research provider unavailable or unconfigured"
        ) from exc
    except WebResearchEvidenceError as exc:
        raise HTTPException(
            status_code=422, detail=str(exc),
        ) from exc
    except LLMError as exc:
        raise HTTPException(
            status_code=502, detail="Web research answer generation failed"
        ) from exc
