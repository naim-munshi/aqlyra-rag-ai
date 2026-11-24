"""Prove OTP resends cannot bypass cooldown through parallel API workers."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.connection import SessionLocal
from app.models.email_verification_code import EmailVerificationCode
from app.models.user import User
from app.services.email_verification_service import (
    VerificationResendTooSoonError,
    issue_verification_code,
)


def test_parallel_otp_requests_issue_only_one_active_challenge(
    client: TestClient,
    db_session: Session,
):
    registered = client.post("/api/v1/auth/register", json={
        "username": "parallelotp",
        "email": "parallelotp@example.com",
        "password": "OtpSafetyPass123!",
    })
    assert registered.status_code == 201
    user_id = registered.json()["id"]
    barrier = Barrier(2)

    def request_code() -> str:
        # Independent sessions mirror distinct FastAPI worker requests.
        with SessionLocal() as session:
            user = session.get(User, user_id)
            assert user is not None
            barrier.wait(timeout=10)
            try:
                issue_verification_code(
                    session, user=user, enforce_cooldown=True,
                )
            except VerificationResendTooSoonError:
                session.rollback()
                return "cooldown"
            return "issued"

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(request_code) for _ in range(2)]
        results = sorted(f.result(timeout=20) for f in futures)

    assert results == ["cooldown", "issued"]
    active = db_session.scalar(
        select(func.count())
        .select_from(EmailVerificationCode)
        .where(
            EmailVerificationCode.user_id == user_id,
            EmailVerificationCode.consumed_at.is_(None),
        )
    )
    assert active == 1
