from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.security import (
    InvalidVerificationTokenError,
    create_access_token,
    create_email_verification_token,
    decode_email_verification_token,
)
from app.core.rate_limit import (
    limit_login_identity,
    limit_login_request,
    limit_resend_request,
    limit_register_request,
    limit_verify_request,
)
from app.config.settings import settings
from app.database.connection import get_db
from app.schemas.auth import (
    EmailVerificationRequest,
    EmailVerificationResendRequest,
    GoogleCredentialRequest,
    RegistrationResponse,
    TokenResponse,
    VerificationDispatchResponse,
)
from app.schemas.user import UserCreate, UserLogin, UserResponse
from app.services.email_service import (
    EmailDeliveryError,
    send_verification_email,
)
from app.services.email_verification_service import (
    VerificationCodeError,
    VerificationResendTooSoonError,
    discard_verification_code,
    issue_verification_code,
    verify_email_code,
)
from app.services.google_identity_service import (
    InvalidGoogleCredentialError,
    verify_google_credential,
)
from app.services.user_service import (
    DuplicateUserError,
    authenticate_user,
    create_user,
    get_or_create_google_user,
    get_user_by_email,
)

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


@router.post(
    "/register",
    response_model=RegistrationResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(limit_register_request),
    ],
)
def register_user(
    user_data: UserCreate,
    db: Session = Depends(get_db),
) -> RegistrationResponse:
    try:
        user = create_user(
            db=db,
            user_data=user_data,
            email_verified=(
                not settings.EMAIL_VERIFICATION_REQUIRED
            ),
        )

        verification_email_sent = False
        verification_token: str | None = None

        if settings.EMAIL_VERIFICATION_REQUIRED:
            issued_code = issue_verification_code(
                db,
                user=user,
                enforce_cooldown=False,
            )
            try:
                send_verification_email(
                    recipient_email=user.email,
                    code=issued_code.code,
                )
                verification_email_sent = True
                verification_token = (
                    create_email_verification_token(
                        subject=str(user.id),
                        challenge_id=(
                            issued_code.challenge_id
                        ),
                    )
                )
            except EmailDeliveryError:
                discard_verification_code(
                    db,
                    challenge_id=issued_code.challenge_id,
                )
                verification_email_sent = False

        return RegistrationResponse(
            **UserResponse.model_validate(
                user
            ).model_dump(),
            verification_required=(
                settings.EMAIL_VERIFICATION_REQUIRED
            ),
            verification_email_sent=(
                verification_email_sent
            ),
            verification_token=(
                verification_token
            ),
        )

    except DuplicateUserError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[
        Depends(limit_login_request),
    ],
)
def login_user(
    login_data: UserLogin,
    db: Session = Depends(get_db),
) -> TokenResponse:
    user = authenticate_user(
        db=db,
        email=str(login_data.email),
        password=login_data.password,
    )

    if user is None:
        limit_login_identity(
            str(login_data.email)
        )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={
                "WWW-Authenticate": "Bearer",
            },
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    if (
        settings.EMAIL_VERIFICATION_REQUIRED
        and user.email_verified_at is None
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email verification required",
        )

    access_token = create_access_token(
        subject=str(user.id),
    )

    return TokenResponse(
        access_token=access_token,
    )


@router.post(
    "/verify-email",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[
        Depends(limit_verify_request),
    ],
)
def verify_email(
    request_data: EmailVerificationRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    try:
        user_id, challenge_id = (
            decode_email_verification_token(
                request_data.verification_token
            )
        )
        user = verify_email_code(
            db,
            user_id=user_id,
            challenge_id=challenge_id,
            code=request_data.code,
        )
    except (
        InvalidVerificationTokenError,
        VerificationCodeError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    return TokenResponse(
        access_token=create_access_token(
            subject=str(user.id),
        )
    )


@router.post(
    "/resend-verification",
    response_model=VerificationDispatchResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[
        Depends(limit_resend_request),
    ],
)
def resend_verification(
    request_data: EmailVerificationResendRequest,
    db: Session = Depends(get_db),
) -> VerificationDispatchResponse:
    generic_message = (
        "If the account is awaiting verification, "
        "a new code has been sent."
    )
    user = get_user_by_email(
        db,
        str(request_data.email).strip().lower(),
    )

    if user is None or user.email_verified_at is not None:
        return VerificationDispatchResponse(
            message=generic_message
        )

    try:
        issued_code = issue_verification_code(
            db,
            user=user,
            enforce_cooldown=True,
        )
    except VerificationResendTooSoonError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Please wait before requesting another code",
            headers={
                "Retry-After": str(exc.retry_after),
            },
        ) from exc

    try:
        send_verification_email(
            recipient_email=user.email,
            code=issued_code.code,
        )
    except EmailDeliveryError as exc:
        discard_verification_code(
            db,
            challenge_id=issued_code.challenge_id,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Verification email is temporarily unavailable",
        ) from exc

    return VerificationDispatchResponse(
        message=generic_message,
        verification_token=(
            create_email_verification_token(
                subject=str(user.id),
                challenge_id=issued_code.challenge_id,
            )
        ),
    )


@router.post(
    "/google",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[
        Depends(limit_login_request),
    ],
)
def google_login(
    request_data: GoogleCredentialRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    try:
        identity = verify_google_credential(
            request_data.credential
        )
        user = get_or_create_google_user(
            db,
            google_subject=identity.subject,
            email=identity.email,
        )
    except InvalidGoogleCredentialError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Google credential",
        ) from exc
    except DuplicateUserError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    return TokenResponse(
        access_token=create_access_token(
            subject=str(user.id),
        )
    )
