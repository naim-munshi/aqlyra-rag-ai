from email.message import EmailMessage
from email.utils import formataddr
import smtplib
import ssl

import httpx

from app.config.settings import settings


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
    if not api_key or not settings.SMTP_FROM_EMAIL.strip():
        raise EmailDeliveryError("Email delivery is not configured")

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
