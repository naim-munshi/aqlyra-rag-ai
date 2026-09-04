from email.message import EmailMessage
from email.utils import formataddr
import smtplib
import ssl

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

    if not username or not password or not from_email:
        raise EmailDeliveryError(
            "Email delivery is not configured"
        )

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
                smtp.starttls(context=tls_context)
                smtp.ehlo()
                smtp.login(username, password)
                smtp.send_message(message)
    except (OSError, smtplib.SMTPException) as exc:
        raise EmailDeliveryError(
            "Verification email delivery failed"
        ) from exc
