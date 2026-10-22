"""SMTP transport security and local Mailpit integration boundaries."""

from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from app.config.settings import Settings, settings
from app.services import email_service


def _mock_connection(monkeypatch, *, use_ssl: bool, starttls: bool):
    monkeypatch.setattr(settings, "SMTP_HOST", "mailpit")
    monkeypatch.setattr(settings, "SMTP_PORT", 1025)
    monkeypatch.setattr(settings, "SMTP_USERNAME", "local@aqlyra.invalid")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", "local-placeholder")
    monkeypatch.setattr(settings, "SMTP_FROM_EMAIL", "local@aqlyra.invalid")
    monkeypatch.setattr(settings, "SMTP_USE_SSL", use_ssl)
    monkeypatch.setattr(settings, "SMTP_STARTTLS", starttls)
    smtp = MagicMock()
    monkeypatch.setattr(email_service.smtplib, "SMTP", smtp)
    smtp_ssl = MagicMock()
    monkeypatch.setattr(email_service.smtplib, "SMTP_SSL", smtp_ssl)
    email_service.send_verification_email(
        recipient_email="test@example.com",
        code="123456",
    )
    return smtp, smtp_ssl


def test_mailpit_local_plain_smtp_does_not_attempt_starttls(monkeypatch):
    smtp, smtp_ssl = _mock_connection(
        monkeypatch, use_ssl=False, starttls=False
    )
    session = smtp.return_value.__enter__.return_value
    session.starttls.assert_not_called()
    session.login.assert_called_once_with(
        "local@aqlyra.invalid", "local-placeholder"
    )
    session.send_message.assert_called_once()
    smtp_ssl.assert_not_called()


def test_regular_smtp_still_upgrades_with_starttls(monkeypatch):
    smtp, smtp_ssl = _mock_connection(
        monkeypatch, use_ssl=False, starttls=True
    )
    session = smtp.return_value.__enter__.return_value
    session.starttls.assert_called_once()
    session.login.assert_called_once()
    smtp_ssl.assert_not_called()


def test_implicit_tls_smtp_remains_supported(monkeypatch):
    smtp, smtp_ssl = _mock_connection(
        monkeypatch, use_ssl=True, starttls=True
    )
    smtp.assert_not_called()
    ssl_session = smtp_ssl.return_value.__enter__.return_value
    ssl_session.login.assert_called_once()
    ssl_session.send_message.assert_called_once()


def test_production_cannot_disable_both_tls_options():
    params = settings.model_dump()
    params.update({
        "APP_ENV": "production",
        "SMTP_USE_SSL": False,
        "SMTP_STARTTLS": False,
    })
    with pytest.raises(ValidationError, match="Production SMTP requires SSL or STARTTLS"):
        Settings.model_validate(params)


def test_local_development_allows_mailpit_without_tls():
    params = settings.model_dump()
    params.update({
        "APP_ENV": "development",
        "SMTP_USE_SSL": False,
        "SMTP_STARTTLS": False,
    })
    assert Settings.model_validate(params).SMTP_STARTTLS is False
