"""Resend HTTPS delivery must not weaken legacy SMTP or disclose OTP codes."""
from types import SimpleNamespace

import httpx
import pytest
from pydantic import ValidationError

from app.config.settings import Settings
from app.services import email_service as mail


@pytest.fixture
def resend(monkeypatch):
    monkeypatch.setattr(mail.settings, "EMAIL_DELIVERY_PROVIDER", "resend")
    monkeypatch.setattr(mail.settings, "RESEND_API_KEY", "test-resend-secret")
    monkeypatch.setattr(mail.settings, "SMTP_FROM_EMAIL", "verify@aqlyra.example")
    monkeypatch.setattr(mail.settings, "SMTP_FROM_NAME", "Aqlyra")
    monkeypatch.setattr(mail.settings, "SMTP_USERNAME", "")
    monkeypatch.setattr(mail.settings, "SMTP_PASSWORD", "")


def test_https_verification_email_without_smtp(monkeypatch, resend):
    calls = []

    def mock_post(url, **kwargs):
        calls.append((url, kwargs))
        return SimpleNamespace(status_code=200)

    monkeypatch.setattr(mail.httpx, "post", mock_post)
    monkeypatch.setattr(mail.smtplib, "SMTP_SSL", lambda *a, **k: (_ for _ in ()).throw(AssertionError("SMTP must not be called")))
    mail.send_verification_email(recipient_email="account@example.com", code="928461")

    assert len(calls) == 1
    url, params = calls[0]
    assert url == "https://api.resend.com/emails"
    assert params["headers"]["Authorization"] == "Bearer test-resend-secret"
    assert params["headers"]["User-Agent"]
    assert params["follow_redirects"] is False
    assert params["json"]["to"] == ["account@example.com"]
    assert "928461" in params["json"]["text"]
    assert "test-resend-secret" not in params["json"]["text"]
    assert params["json"]["subject"] == "Your Aqlyra verification code"


def test_https_reset_email_without_smtp(monkeypatch, resend):
    sent = []

    def mock_post(url, **kwargs):
        sent.append(kwargs["json"])
        return SimpleNamespace(status_code=200)

    monkeypatch.setattr(mail.httpx, "post", mock_post)
    mail.send_password_reset_email(recipient_email="owner@example.com", code="123456")

    assert len(sent) == 1
    assert sent[0]["to"] == ["owner@example.com"]
    assert "123456" in sent[0]["text"]
    assert sent[0]["subject"] == "Reset your Aqlyra password"


@pytest.mark.parametrize("code", [301, 400, 401, 429, 500])
def test_provider_failure_is_fail_closed_and_sanitized(monkeypatch, resend, code):
    monkeypatch.setattr(
        mail.httpx, "post",
        lambda *args, **kwargs: SimpleNamespace(status_code=code, text="sensitive-provider-response"),
    )
    with pytest.raises(mail.EmailDeliveryError) as err:
        mail.send_verification_email(recipient_email="owner@example.com", code="999999")
    assert "999999" not in str(err.value)
    assert "sensitive-provider-response" not in str(err.value)
    assert "test-resend-secret" not in str(err.value)


def test_network_error_is_fail_closed(monkeypatch, resend):
    def fail(*args, **kwargs):
        raise httpx.ConnectError("cannot connect")

    monkeypatch.setattr(mail.httpx, "post", fail)
    with pytest.raises(mail.EmailDeliveryError, match="delivery failed"):
        mail.send_password_reset_email(recipient_email="user@example.com", code="123456")


@pytest.mark.parametrize(
    "invalid_sender",
    ["Aqlyra", "Aqlyra <verify@example.com>", "not-an-email", "foo@"],
)
def test_resend_invalid_sender_fails_before_network(monkeypatch, resend, invalid_sender):
    # A production misconfiguration previously sent "Aqlyra <Aqlyra>"
    # to the provider and stranded registrations behind HTTP 422.
    monkeypatch.setattr(mail.settings, "SMTP_FROM_EMAIL", invalid_sender)
    monkeypatch.setattr(
        mail.httpx,
        "post",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("invalid sender sent to Resend")),
    )
    with pytest.raises(mail.EmailDeliveryError, match="sender is misconfigured"):
        mail.send_verification_email(
            recipient_email="account@example.com",
            code="123456",
        )
    with pytest.raises(mail.EmailDeliveryError, match="sender is misconfigured"):
        mail.send_password_reset_email(
            recipient_email="account@example.com",
            code="654321",
        )


def test_missing_resend_key_fails_before_network(monkeypatch, resend):
    monkeypatch.setattr(mail.settings, "RESEND_API_KEY", "")
    monkeypatch.setattr(mail.httpx, "post", lambda *a, **k: (_ for _ in ()).throw(AssertionError("unexpected outbound HTTP")))
    with pytest.raises(mail.EmailDeliveryError, match="not configured"):
        mail.send_verification_email(recipient_email="user@example.com", code="123456")


def test_unknown_provider_rejected():
    with pytest.raises(ValidationError, match="EMAIL_DELIVERY_PROVIDER"):
        Settings(EMAIL_DELIVERY_PROVIDER="unsafe-provider", _env_file=None)


def test_legacy_smtp_remains_default():
    assert Settings(_env_file=None).EMAIL_DELIVERY_PROVIDER == "smtp"


@pytest.fixture
def brevo(monkeypatch):
    monkeypatch.setattr(mail.settings, "EMAIL_DELIVERY_PROVIDER", "brevo")
    monkeypatch.setattr(mail.settings, "BREVO_API_KEY", "test-brevo-secret")
    monkeypatch.setattr(mail.settings, "SMTP_FROM_EMAIL", "aqlyra.verify@gmail.com")
    monkeypatch.setattr(mail.settings, "SMTP_FROM_NAME", "Aqlyra")
    monkeypatch.setattr(mail.settings, "SMTP_USERNAME", "")
    monkeypatch.setattr(mail.settings, "SMTP_PASSWORD", "")


def test_brevo_https_sends_registration_and_reset_without_smtp(monkeypatch, brevo):
    requests = []

    def mock_post(url, **kwargs):
        requests.append((url, kwargs))
        return SimpleNamespace(status_code=201)

    monkeypatch.setattr(mail.httpx, "post", mock_post)
    monkeypatch.setattr(
        mail.smtplib, "SMTP_SSL",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("No SMTP")),
    )
    mail.send_verification_email(
        recipient_email="student@example.com", code="123456"
    )
    mail.send_password_reset_email(
        recipient_email="student@example.com", code="654321"
    )

    assert len(requests) == 2
    assert all(url == "https://api.brevo.com/v3/smtp/email" for url, _ in requests)
    for _, params in requests:
        assert params["headers"]["api-key"] == "test-brevo-secret"
        assert params["follow_redirects"] is False
        assert params["json"]["sender"] == {
            "name": "Aqlyra",
            "email": "aqlyra.verify@gmail.com",
        }
        assert params["json"]["to"] == [{"email": "student@example.com"}]
        assert "test-brevo-secret" not in params["json"]["textContent"]
    assert "123456" in requests[0][1]["json"]["textContent"]
    assert "654321" in requests[1][1]["json"]["textContent"]


@pytest.mark.parametrize("status_code", [200, 301, 400, 401, 403, 429, 500])
def test_brevo_rejection_fails_closed(monkeypatch, brevo, status_code):
    monkeypatch.setattr(
        mail.httpx,
        "post",
        lambda *a, **k: SimpleNamespace(
            status_code=status_code, text="private-provider-error"
        ),
    )
    with pytest.raises(mail.EmailDeliveryError) as exc:
        mail.send_verification_email(
            recipient_email="student@example.com", code="123456"
        )
    for secret in ("123456", "test-brevo-secret", "private-provider-error"):
        assert secret not in str(exc.value)


def test_brevo_missing_credentials_and_malformed_sender_fail_pre_network(
    monkeypatch, brevo,
):
    monkeypatch.setattr(
        mail.httpx, "post",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("No outbound request")),
    )
    monkeypatch.setattr(mail.settings, "BREVO_API_KEY", "")
    with pytest.raises(mail.EmailDeliveryError, match="not configured"):
        mail.send_password_reset_email(
            recipient_email="student@example.com", code="654321"
        )

    monkeypatch.setattr(mail.settings, "BREVO_API_KEY", "test-brevo-secret")
    monkeypatch.setattr(mail.settings, "SMTP_FROM_EMAIL", "Aqlyra")
    with pytest.raises(mail.EmailDeliveryError, match="sender is misconfigured"):
        mail.send_verification_email(
            recipient_email="student@example.com", code="123456"
        )


def test_brevo_network_failure_fails_closed(monkeypatch, brevo):
    def fail(*args, **kwargs):
        raise httpx.ConnectError("offline")
    monkeypatch.setattr(mail.httpx, "post", fail)
    with pytest.raises(mail.EmailDeliveryError, match="delivery failed"):
        mail.send_password_reset_email(
            recipient_email="student@example.com", code="654321"
        )

