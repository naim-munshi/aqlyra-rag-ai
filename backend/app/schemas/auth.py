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


class EmailVerificationChallenge(BaseModel):
    code: str = Field(
        min_length=6,
        max_length=6,
        pattern=r"^[0-9]{6}$",
    )
    verification_token: str = Field(
        min_length=20,
        max_length=2_000,
    )


class EmailVerificationRequest(EmailVerificationChallenge):
    password: str = Field(min_length=8, max_length=72)


class PendingEmailClaimRequest(EmailVerificationChallenge):
    """Mailbox proof is required to replace a pending registration."""
    username: str = Field(
        min_length=3,
        max_length=50,
        pattern=r"^[a-zA-Z0-9_-]+$",
    )
    new_password: str = Field(min_length=8, max_length=72)


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

class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirmRequest(BaseModel):
    email: EmailStr
    code: str = Field(min_length=6, max_length=6, pattern=r"^[0-9]{6}$")
    new_password: str = Field(min_length=8, max_length=72)


class PasswordResetMessage(BaseModel):
    message: str


class PasswordResetAuthenticatedResponse(TokenResponse):
    message: str
