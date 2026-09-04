from dataclasses import dataclass

from app.config.settings import settings


@dataclass(frozen=True)
class GoogleIdentity:
    subject: str
    email: str


class InvalidGoogleCredentialError(Exception):
    """Raised when Google cannot verify an identity token."""


def verify_google_credential(
    credential: str,
) -> GoogleIdentity:
    client_id = settings.GOOGLE_CLIENT_ID.strip()

    if not client_id:
        raise InvalidGoogleCredentialError(
            "Google sign-in is not configured"
        )

    try:
        from google.auth.exceptions import GoogleAuthError
        from google.auth.transport.requests import Request
        from google.oauth2 import id_token

        claims = id_token.verify_oauth2_token(
            credential,
            Request(),
            client_id,
        )
    except ImportError as exc:
        raise InvalidGoogleCredentialError(
            "Google sign-in is unavailable"
        ) from exc
    except (ValueError, GoogleAuthError) as exc:
        raise InvalidGoogleCredentialError(
            "Invalid Google credential"
        ) from exc

    issuer = claims.get("iss")
    subject = claims.get("sub")
    email = claims.get("email")
    email_verified = claims.get("email_verified")

    if issuer not in {
        "accounts.google.com",
        "https://accounts.google.com",
    }:
        raise InvalidGoogleCredentialError(
            "Invalid Google credential"
        )

    if (
        not isinstance(subject, str)
        or not subject.strip()
        or not isinstance(email, str)
        or not email.strip()
        or email_verified not in {True, "true"}
    ):
        raise InvalidGoogleCredentialError(
            "Google email is not verified"
        )

    return GoogleIdentity(
        subject=subject.strip(),
        email=email.strip().lower(),
    )
