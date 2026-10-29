from email.message import EmailMessage
import base64
import logging
from email.utils import formataddr
import smtplib
import ssl

import httpx
from email_validator import EmailNotValidError, validate_email

from app.config.settings import settings


_logger = logging.getLogger(__name__)

# Never print arbitrary Gmail API errors: response bodies can contain
# account metadata. Only these documented/reviewed error classes may
# enter operator logs; every other reason is reduced to "unspecified".
_SAFE_GMAIL_FAILURE_REASONS = frozenset({
    "insufficientPermissions", "accessNotConfigured", "forbidden",
    "rateLimitExceeded", "userRateLimitExceeded", "dailyLimitExceeded",
    "quotaExceeded", "failedPrecondition",
    "PERMISSION_DENIED", "RESOURCE_EXHAUSTED", "UNAUTHENTICATED",
    "FAILED_PRECONDITION",
})


def _safe_gmail_failure_reason(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except (AttributeError, TypeError, ValueError):
        return "unspecified"
    if not isinstance(payload, dict):
        return "unspecified"
    error = payload.get("error")
    if not isinstance(error, dict):
        return "unspecified"
    reasons = error.get("errors")
    candidate = None
    if isinstance(reasons, list) and reasons and isinstance(reasons[0], dict):
        candidate = reasons[0].get("reason")
    if candidate not in _SAFE_GMAIL_FAILURE_REASONS:
        candidate = error.get("status")
    return candidate if candidate in _SAFE_GMAIL_FAILURE_REASONS else "unspecified"


class EmailDeliveryError(Exception):
    """Raised when a verification email cannot be delivered."""


def send_verification_email(
    *,
    recipient_email: str,
    code: str,
) -> None:
    username = settings.SMTP_USERNAME.strip()
    password = settings.SMTP_PASSWORD.strip()
    from_email = (
        settings.SMTP_FROM_EMAIL.strip()
        or username
    )

    if not from_email or (
        settings.EMAIL_DELIVERY_PROVIDER == "smtp"
        and (not username or not password)
    ):
        raise EmailDeliveryError("Email delivery is not configured")

    message = EmailMessage()
    message["Subject"] = "Your Aqlyra verification code"
    message["From"] = formataddr(
        (
            settings.SMTP_FROM_NAME.strip(),
            from_email,
        )
    )
    message["To"] = recipient_email
    message.set_content(
        "Welcome to Aqlyra.\n\n"
        f"Your verification code is: {code}\n\n"
        "This code expires in "
        f"{settings.EMAIL_VERIFICATION_CODE_TTL_MINUTES} "
        "minutes. If you did not request this code, "
        "you can ignore this email."
    )

    _send_message(message, username, password)


def _send_message(message: EmailMessage, username: str, password: str) -> None:
    if settings.EMAIL_DELIVERY_PROVIDER == "resend":
        _send_via_resend(message)
        return
    if settings.EMAIL_DELIVERY_PROVIDER == "brevo":
        _send_via_brevo(message)
        return
    if settings.EMAIL_DELIVERY_PROVIDER == "gmail_api":
        _send_via_gmail_api(message)
        return

    tls_context = ssl.create_default_context()

    try:
        if settings.SMTP_USE_SSL:
            with smtplib.SMTP_SSL(
                settings.SMTP_HOST,
                settings.SMTP_PORT,
                timeout=settings.SMTP_TIMEOUT_SECONDS,
                context=tls_context,
            ) as smtp:
                smtp.login(username, password)
                smtp.send_message(message)
        else:
            with smtplib.SMTP(
                settings.SMTP_HOST,
                settings.SMTP_PORT,
                timeout=settings.SMTP_TIMEOUT_SECONDS,
            ) as smtp:
                smtp.ehlo()
                if settings.SMTP_STARTTLS:
                    smtp.starttls(context=tls_context)
                    smtp.ehlo()
                smtp.login(username, password)
                smtp.send_message(message)
    except (OSError, smtplib.SMTPException) as exc:
        raise EmailDeliveryError(
            "Authentication email delivery failed"
        ) from exc


def _send_via_resend(message: EmailMessage) -> None:
    """HTTPS transactional email for serverless hosts without SMTP ports."""
    api_key = settings.RESEND_API_KEY.strip()
    sender_address = settings.SMTP_FROM_EMAIL.strip()
    if not api_key or not sender_address:
        raise EmailDeliveryError("Email delivery is not configured")

    # SMTP_FROM_NAME is the display name; SMTP_FROM_EMAIL must contain only
    # a mailbox. A value such as "Aqlyra" previously produced
    # "Aqlyra <Aqlyra>" and a Resend 422 for every verification email.
    try:
        validate_email(sender_address, check_deliverability=False)
    except EmailNotValidError as exc:
        raise EmailDeliveryError("Email sender is misconfigured") from exc

    recipient = message.get("To")
    subject = message.get("Subject")
    if not recipient or not subject:
        raise EmailDeliveryError("Invalid outgoing email metadata")
    try:
        response = httpx.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {api_key}",
                "User-Agent": "Aqlyra-RAG-AI/1.0",
                "Accept": "application/json",
            },
            json={
                "from": str(message["From"]),
                "to": [str(recipient)],
                "subject": str(subject),
                "text": message.get_content(),
            },
            timeout=settings.SMTP_TIMEOUT_SECONDS,
            follow_redirects=False,
        )
    except httpx.HTTPError as exc:
        raise EmailDeliveryError("Authentication email delivery failed") from exc
    if response.status_code != 200:
        # Never leak the provider response: it may include sensitive metadata.
        raise EmailDeliveryError("Authentication email delivery failed")


def _send_via_brevo(message: EmailMessage) -> None:
    """Opt-in HTTPS transactional email, usable on hosts without SMTP ports."""
    api_key = settings.BREVO_API_KEY.strip()
    sender_address = settings.SMTP_FROM_EMAIL.strip()
    if not api_key or not sender_address:
        raise EmailDeliveryError("Email delivery is not configured")

    # The Brevo sender must already be verified in the owner's Brevo account.
    # Public-domain senders (Gmail) may be rewritten by Brevo for DMARC.
    try:
        validate_email(sender_address, check_deliverability=False)
    except EmailNotValidError as exc:
        raise EmailDeliveryError("Email sender is misconfigured") from exc

    recipient = message.get("To")
    subject = message.get("Subject")
    if not recipient or not subject:
        raise EmailDeliveryError("Invalid outgoing email metadata")

    try:
        response = httpx.post(
            "https://api.brevo.com/v3/smtp/email",
            headers={
                "api-key": api_key,
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "Aqlyra-RAG-AI/1.0",
            },
            json={
                "sender": {
                    "name": settings.SMTP_FROM_NAME.strip(),
                    "email": sender_address,
                },
                "to": [{"email": str(recipient)}],
                "subject": str(subject),
                "textContent": message.get_content(),
            },
            timeout=settings.SMTP_TIMEOUT_SECONDS,
            follow_redirects=False,
        )
    except httpx.HTTPError as exc:
        raise EmailDeliveryError("Authentication email delivery failed") from exc

    # A 201 means accepted for delivery, not inbox receipt.
    if response.status_code != 201:
        # Never expose the provider response, email address, OTP, or API key.
        raise EmailDeliveryError("Authentication email delivery failed")


def _send_via_gmail_api(message: EmailMessage) -> None:
    """Send via authorized Gmail HTTPS OAuth, not blocked production SMTP ports.

    Gmail API being *enabled* is not sufficient: the owner must grant the
    gmail.send scope to this server's OAuth client and supply an offline
    refresh token through private host environment variables.
    """
    sender_address = settings.SMTP_FROM_EMAIL.strip()
    client_id = settings.GMAIL_OAUTH_CLIENT_ID.strip()
    client_secret = settings.GMAIL_OAUTH_CLIENT_SECRET.strip()
    refresh_token = settings.GMAIL_OAUTH_REFRESH_TOKEN.strip()
    if not all((sender_address, client_id, client_secret, refresh_token)):
        raise EmailDeliveryError("Email delivery is not configured")
    try:
        validate_email(sender_address, check_deliverability=False)
    except EmailNotValidError as exc:
        raise EmailDeliveryError("Email sender is misconfigured") from exc

    if not message.get("To") or not message.get("Subject"):
        raise EmailDeliveryError("Invalid outgoing email metadata")

    try:
        token_response = httpx.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
            timeout=settings.SMTP_TIMEOUT_SECONDS,
            follow_redirects=False,
        )
        if token_response.status_code != 200:
            raise EmailDeliveryError("Authentication email delivery failed")
        token_payload = token_response.json()
        access_token = token_payload.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            raise EmailDeliveryError("Authentication email delivery failed")

        encoded_message = base64.urlsafe_b64encode(
            message.as_bytes()
        ).decode("ascii")
        send_response = httpx.post(
            "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            json={"raw": encoded_message},
            timeout=settings.SMTP_TIMEOUT_SECONDS,
            follow_redirects=False,
        )
        if send_response.status_code != 200:
            _logger.warning(
                "gmail_send_rejected status=%s reason=%s",
                send_response.status_code,
                _safe_gmail_failure_reason(send_response),
            )
            raise EmailDeliveryError("Authentication email delivery failed")
        result = send_response.json()
        if not isinstance(result, dict) or not result.get("id"):
            raise EmailDeliveryError("Authentication email delivery failed")
    except (httpx.HTTPError, ValueError, TypeError) as exc:
        # Do not leak OAuth tokens, email contents, or provider response bodies.
        raise EmailDeliveryError("Authentication email delivery failed") from exc


def send_password_reset_email(*, recipient_email: str, code: str) -> None:
    username = settings.SMTP_USERNAME.strip()
    password = settings.SMTP_PASSWORD.strip()
    from_email = settings.SMTP_FROM_EMAIL.strip() or username
    if not from_email or (
        settings.EMAIL_DELIVERY_PROVIDER == "smtp"
        and (not username or not password)
    ):
        raise EmailDeliveryError("Email delivery is not configured")

    message = EmailMessage()
    message["Subject"] = "Reset your Aqlyra password"
    message["From"] = formataddr((settings.SMTP_FROM_NAME.strip(), from_email))
    message["To"] = recipient_email
    message.set_content(
        "You requested to reset your Aqlyra password.\n\n"
        f"Your password reset code is: {code}\n\n"
        f"This code expires in {settings.PASSWORD_RESET_CODE_TTL_MINUTES} minutes. "
        "If you did not request this, ignore this email. "
        "Never share this code with anyone."
    )
    _send_message(message, username, password)
