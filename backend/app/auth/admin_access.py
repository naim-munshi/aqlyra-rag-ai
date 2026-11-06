"""Single verified-admin decision shared by /users/me and protected admin routes."""
from app.config.settings import settings
from app.models.user import User


def is_privileged_identity(user: User) -> bool:
    """Conservatively protect both active and pending admin identities."""
    configured_ids = settings.ADMIN_USER_IDS.split(",")
    exact_email = settings.ADMIN_OWNER_EMAIL
    return user.id in configured_ids or bool(
        exact_email and user.email.strip().lower() == exact_email
    )


def is_admin_user(user: User) -> bool:
    """Server-side authority only; email requires mailbox verification."""
    return bool(
        user.is_active
        and user.email_verified_at is not None
        and is_privileged_identity(user)
    )
