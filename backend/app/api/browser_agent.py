"""Browser automation is opt-in, authenticated and requires separate approval."""
from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_current_user
from app.core.rate_limit import limit_rag_request
from app.llms.types import LLMError
from app.models.user import User
from app.schemas.browser_agent import (
    BrowserExecuteRequest, BrowserPlanRequest, BrowserPlanResponse, BrowserRunResponse,
)
from app.services.browser_agent_service import (
    BrowserAgentPlanError, BrowserAgentUnavailable,
    create_browser_plan, execute_browser_plan,
)

router = APIRouter(prefix="/agent/browser", tags=["Browser Agent"])


@router.post(
    "/plan",
    response_model=BrowserPlanResponse,
    dependencies=[Depends(limit_rag_request)],
)
def plan_browser_job(
    body: BrowserPlanRequest,
    user: User = Depends(get_current_user),
) -> BrowserPlanResponse:
    try:
        return create_browser_plan(body.task, body.start_url, str(user.id))
    except BrowserAgentPlanError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except BrowserAgentUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post(
    "/execute",
    response_model=BrowserRunResponse,
    dependencies=[Depends(limit_rag_request)],
)
async def execute_browser_job(
    body: BrowserExecuteRequest,
    user: User = Depends(get_current_user),
) -> BrowserRunResponse:
    if body.approved is not True:
        raise HTTPException(status_code=400, detail="Explicit user approval is required")
    try:
        return await execute_browser_plan(body.plan_token, str(user.id))
    except BrowserAgentPlanError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except BrowserAgentUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except LLMError as exc:
        raise HTTPException(status_code=502, detail="Configured AI provider failed") from exc
