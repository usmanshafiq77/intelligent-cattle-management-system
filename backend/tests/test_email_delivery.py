from datetime import datetime, timezone
import smtplib

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.services import email_delivery
from app.services.email_delivery import EmailDeliveryError, SMTPEmailSender


def make_sender(**overrides):
    values = {
        "host": "smtp.example.test",
        "port": 587,
        "username": "mailer@example.test",
        "password": "app-password",
        "use_starttls": True,
        "use_ssl": False,
        "sender_email": "mailer@example.test",
        "sender_name": "ICMS",
        "verification_base_url": "https://app.example.test/auth/verify-email",
        "password_reset_base_url": "https://app.example.test/reset-password",
        "invitation_accept_base_url": "https://app.example.test/invitations/accept",
        "timeout_seconds": 7,
        "max_attempts": 3,
        "retry_delay_seconds": 0,
    }
    values.update(overrides)
    return SMTPEmailSender(**values)


class RecordingSMTP:
    instances = []
    send_failures = []

    def __init__(self, host, port, **kwargs):
        self.host = host
        self.port = port
        self.kwargs = kwargs
        self.events = []
        self.message = None
        type(self).instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def ehlo(self):
        self.events.append("ehlo")

    def starttls(self, **kwargs):
        self.events.append("starttls")

    def login(self, username, password):
        self.events.append(("login", username, password))

    def send_message(self, message):
        self.message = message
        if type(self).send_failures:
            raise type(self).send_failures.pop(0)
        self.events.append("sent")
        return {}


@pytest.fixture(autouse=True)
def reset_smtp_double():
    RecordingSMTP.instances = []
    RecordingSMTP.send_failures = []


def test_smtp_verification_uses_starttls_auth_and_frontend_link(monkeypatch):
    monkeypatch.setattr(smtplib, "SMTP", RecordingSMTP)
    sender = make_sender()
    sender.send_verification_email(
        recipient="farmer@example.test",
        token="verification-secret-token",
        expires_at=datetime(2026, 10, 23, tzinfo=timezone.utc),
    )

    connection = RecordingSMTP.instances[0]
    assert connection.host == "smtp.example.test"
    assert connection.kwargs["timeout"] == 7
    assert connection.events == [
        "ehlo",
        "starttls",
        "ehlo",
        ("login", "mailer@example.test", "app-password"),
        "sent",
    ]
    assert connection.message["To"] == "farmer@example.test"
    assert (
        "https://app.example.test/auth/verify-email?token="
        "verification-secret-token"
    ) in connection.message.get_content()


def test_smtp_templates_cover_reset_and_invitation(monkeypatch):
    monkeypatch.setattr(smtplib, "SMTP", RecordingSMTP)
    sender = make_sender()
    expires = datetime(2026, 10, 23, tzinfo=timezone.utc)

    sender.send_password_reset_email(
        recipient="farmer@example.test",
        token="reset-secret-token",
        expires_at=expires,
    )
    sender.send_invitation_email(
        recipient="worker@example.test",
        token="invite-secret-token",
        expires_at=expires,
        farm_name="Green Farm",
    )

    reset_body = RecordingSMTP.instances[0].message.get_content()
    invite_body = RecordingSMTP.instances[1].message.get_content()
    assert "https://app.example.test/reset-password?token=reset-secret-token" in reset_body
    assert "https://app.example.test/invitations/accept?token=invite-secret-token" in invite_body
    assert "Green Farm" in invite_body


def test_transient_smtp_failure_retries_without_logging_token(monkeypatch):
    monkeypatch.setattr(smtplib, "SMTP", RecordingSMTP)
    RecordingSMTP.send_failures = [TimeoutError("provider timeout")]
    warnings = []
    monkeypatch.setattr(
        email_delivery.logger,
        "warning",
        lambda message, *args: warnings.append(message % args),
    )
    sender = make_sender()

    sender.send_password_reset_email(
        recipient="farmer@example.test",
        token="must-not-appear-in-log",
        expires_at=datetime(2026, 10, 23, tzinfo=timezone.utc),
    )

    assert len(RecordingSMTP.instances) == 2
    assert "must-not-appear-in-log" not in " ".join(warnings)
    assert warnings == ["Transient SMTP delivery failure; retrying attempt 2 of 3"]


def test_permanent_smtp_failure_is_sanitized_and_not_retried(monkeypatch):
    monkeypatch.setattr(smtplib, "SMTP", RecordingSMTP)
    errors = []
    monkeypatch.setattr(
        email_delivery.logger,
        "error",
        lambda message, *args: errors.append(message % args),
    )
    RecordingSMTP.send_failures = [
        smtplib.SMTPAuthenticationError(535, b"credential rejected")
    ]
    sender = make_sender()

    with pytest.raises(EmailDeliveryError, match="SMTP delivery failed") as error:
        sender.send_verification_email(
            recipient="farmer@example.test",
            token="must-not-escape",
            expires_at=datetime(2026, 10, 23, tzinfo=timezone.utc),
        )

    assert len(RecordingSMTP.instances) == 1
    assert "credential" not in str(error.value)
    assert "must-not-escape" not in str(error.value)
    assert errors == [
        "SMTP delivery failed after 1 attempt(s) "
        "(error_type=SMTPAuthenticationError, smtp_code=535)"
    ]
    assert "credential" not in errors[0]
    assert "must-not-escape" not in errors[0]


def test_smtp_configuration_requires_secure_consistent_values():
    common = {
        "_env_file": None,
        "APP_ENV": "test",
        "DB_PASSWORD": "test-password",
        "JWT_SECRET_KEY": "test-jwt-secret-with-at-least-32-characters",
        "CORS_ALLOWED_ORIGINS": ["http://localhost:8081"],
    }
    with pytest.raises(ValidationError):
        Settings(
            **common,
            EMAIL_DELIVERY_MODE="smtp",
            SMTP_HOST="smtp.example.test",
            SMTP_SENDER_EMAIL="sender@example.test",
            SMTP_USE_STARTTLS=True,
            SMTP_USE_SSL=True,
        )
    with pytest.raises(ValidationError):
        Settings(
            **common,
            EMAIL_DELIVERY_MODE="smtp",
            SMTP_HOST="smtp.example.test",
            SMTP_SENDER_EMAIL="sender@example.test",
            SMTP_USERNAME="sender@example.test",
        )
    with pytest.raises(ValidationError):
        Settings(
            **common,
            EMAIL_DELIVERY_MODE="smtp",
            SMTP_HOST="smtp.example.test",
            SMTP_SENDER_EMAIL="sender@example.test",
            SMTP_USE_STARTTLS=False,
            SMTP_USE_SSL=False,
        )


def test_production_requires_https_smtp_and_nonplaceholder_jwt_secret():
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            APP_ENV="production",
            DB_PASSWORD="test-password",
            JWT_SECRET_KEY="replace_with_a_long_random_secret",
            CORS_ALLOWED_ORIGINS=["https://app.example.test"],
            FRONTEND_PUBLIC_URL="https://app.example.test",
            EMAIL_DELIVERY_MODE="console",
        )
