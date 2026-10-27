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
