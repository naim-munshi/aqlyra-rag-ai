from email.message import EmailMessage
from email.utils import formataddr
import smtplib
import ssl

import httpx
from email_validator import EmailNotValidError, validate_email

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
    if settings.EMAIL_DELIVERY_PROVIDER == "brevo":
        _send_via_brevo(message)
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
