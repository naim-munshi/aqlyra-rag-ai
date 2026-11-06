from fastapi import APIRouter, Depends

from app.api.dependencies import get_current_user
from app.models.user import User
from app.auth.admin_access import is_admin_user
from app.schemas.user import UserResponse


router = APIRouter(
    prefix="/users",
    tags=["Users"],
)


@router.get(
    "/me",
    response_model=UserResponse,
)
def read_current_user(
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    response = UserResponse.model_validate(current_user)
    return response.model_copy(
        update={
            "is_admin": is_admin_user(current_user),
        }
    )