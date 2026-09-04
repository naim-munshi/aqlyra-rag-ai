from typing import Literal

from pydantic import BaseModel, EmailStr, Field

from app.schemas.user import UserResponse


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"


class RegistrationResponse(UserResponse):
    verification_required: bool
    verification_email_sent: bool
    verification_token: str | None = None


class EmailVerificationRequest(BaseModel):
    code: str = Field(
        min_length=6,
        max_length=6,
        pattern=r"^[0-9]{6}$",
    )
    verification_token: str = Field(
        min_length=20,
        max_length=2_000,
    )


class EmailVerificationResendRequest(BaseModel):
    email: EmailStr


class GoogleCredentialRequest(BaseModel):
    credential: str = Field(
        min_length=20,
        max_length=10_000,
    )


class VerificationDispatchResponse(BaseModel):
    message: str
    verification_token: str | None = None
