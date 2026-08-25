from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.database.connection import get_db
from app.models.user import User
from app.schemas.conversation import ConversationMode
from app.schemas.project import ProjectCreate, ProjectResponse, ProjectUpdate
from app.services.project_service import (
    create_project,
    delete_project,
    get_project_for_user,
    list_projects_for_user,
    update_project,
)


router = APIRouter(
    prefix="/projects",
    tags=["Projects"],
)


def _project_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Project not found",
    )


@router.post(
    "",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_project_endpoint(
    request: ProjectCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectResponse:
    return create_project(
        db=db,
        user_id=str(current_user.id),
        name=request.name,
        mode=request.mode,
    )


@router.get(
    "",
    response_model=list[ProjectResponse],
)
def list_projects_endpoint(
    mode: ConversationMode | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ProjectResponse]:
    return list_projects_for_user(
        db=db,
        user_id=str(current_user.id),
        mode=mode,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{project_id}",
    response_model=ProjectResponse,
)
def get_project_endpoint(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectResponse:
    project = get_project_for_user(
        db=db,
        user_id=str(current_user.id),
        project_id=project_id,
    )
    if project is None:
        raise _project_not_found()
    return project


@router.patch(
    "/{project_id}",
    response_model=ProjectResponse,
)
def update_project_endpoint(
    project_id: str,
    request: ProjectUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectResponse:
    project = get_project_for_user(
        db=db,
        user_id=str(current_user.id),
        project_id=project_id,
    )
    if project is None:
        raise _project_not_found()

    return update_project(
        db=db,
        project=project,
        name=request.name,
    )


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_project_endpoint(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    project = get_project_for_user(
        db=db,
        user_id=str(current_user.id),
        project_id=project_id,
    )
    if project is None:
        raise _project_not_found()

    delete_project(
        db=db,
        project=project,
    )
    return Response(
        status_code=status.HTTP_204_NO_CONTENT,
    )
