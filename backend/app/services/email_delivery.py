import logging
import smtplib
import ssl
import time
from datetime import datetime
from email.message import EmailMessage
from email.utils import formataddr
from functools import lru_cache
from typing import Protocol
from urllib.parse import urlencode

from app.core.config import get_settings


logger = logging.getLogger(__name__)


class EmailSender(Protocol):
    def send_verification_email(
        self,
        *,
        recipient: str,
        token: str,
        expires_at: datetime,
    ) -> None: ...

    def send_invitation_email(
        self,
        *,
        recipient: str,
        token: str,
        expires_at: datetime,
        farm_name: str,
    ) -> None: ...

    def send_password_reset_email(
        self,
        *,
        recipient: str,
        token: str,
        expires_at: datetime,
    ) -> None: ...


class EmailDeliveryNotConfiguredError(RuntimeError):
    pass


class EmailDeliveryError(RuntimeError):
    """A sanitized delivery failure safe for application logs and callers."""


def _mask_email(email: str) -> str:
    local, separator, domain = email.partition("@")
    if not separator:
        return "<invalid-email>"
    visible = local[:1] if local else "*"
    return f"{visible}***@{domain}"


def _action_url(base_url: str, token: str) -> str:
    query = urlencode({"token": token})
    separator = "&" if "?" in base_url else "?"
    return f"{base_url}{separator}{query}"


class DevelopmentConsoleEmailSender:
    """Local-only delivery that emits action links to the developer console."""

    def __init__(
        self,
        verification_base_url: str,
        password_reset_base_url: str,
        invitation_accept_base_url: str,
    ) -> None:
        self._verification_base_url = verification_base_url
        self._password_reset_base_url = password_reset_base_url
        self._invitation_accept_base_url = invitation_accept_base_url

    def send_verification_email(
        self,
        *,
        recipient: str,
        token: str,
        expires_at: datetime,
    ) -> None:
        logger.warning(
            "LOCAL DEVELOPMENT ONLY: verification link for %s "
            "(expires %s): %s",
            _mask_email(recipient),
            expires_at.isoformat(),
            _action_url(self._verification_base_url, token),
        )

    def send_invitation_email(
        self,
        *,
        recipient: str,
        token: str,
        expires_at: datetime,
        farm_name: str,
    ) -> None:
        logger.warning(
            "LOCAL DEVELOPMENT ONLY: invitation link for %s "
            "to farm %s (expires %s): %s",
            _mask_email(recipient),
            farm_name,
            expires_at.isoformat(),
            _action_url(self._invitation_accept_base_url, token),
        )

    def send_password_reset_email(
        self,
        *,
        recipient: str,
        token: str,
        expires_at: datetime,
    ) -> None:
        logger.warning(
            "LOCAL DEVELOPMENT ONLY: password reset link for %s "
            "(expires %s): %s",
            _mask_email(recipient),
            expires_at.isoformat(),
            _action_url(self._password_reset_base_url, token),
        )


class SMTPEmailSender:
    """Authenticated SMTP sender with TLS, timeouts, and bounded retries."""

    def __init__(
        self,
        *,
        host: str,
        port: int,
        username: str | None,
        password: str | None,
        use_starttls: bool,
        use_ssl: bool,
        sender_email: str,
        sender_name: str,
        verification_base_url: str,
        password_reset_base_url: str,
        invitation_accept_base_url: str,
        timeout_seconds: float,
        max_attempts: int,
        retry_delay_seconds: float,
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._use_starttls = use_starttls
        self._use_ssl = use_ssl
        self._sender = formataddr((sender_name, sender_email))
        self._verification_base_url = verification_base_url
        self._password_reset_base_url = password_reset_base_url
        self._invitation_accept_base_url = invitation_accept_base_url
        self._timeout_seconds = timeout_seconds
        self._max_attempts = max_attempts
        self._retry_delay_seconds = retry_delay_seconds

    def _message(self, *, recipient: str, subject: str, body: str) -> EmailMessage:
        message = EmailMessage()
        message["From"] = self._sender
        message["To"] = recipient
        message["Subject"] = subject
        message.set_content(body)
        return message

    def _send_once(self, message: EmailMessage) -> None:
        context = ssl.create_default_context()
        smtp_type = smtplib.SMTP_SSL if self._use_ssl else smtplib.SMTP
        kwargs = {"timeout": self._timeout_seconds}
        if self._use_ssl:
            kwargs["context"] = context

        with smtp_type(self._host, self._port, **kwargs) as connection:
            connection.ehlo()
            if self._use_starttls:
                connection.starttls(context=context)
                connection.ehlo()
            if self._username and self._password:
                connection.login(self._username, self._password)
            refused = connection.send_message(message)
            if refused:
                raise smtplib.SMTPRecipientsRefused(refused)

    @staticmethod
    def _is_transient(error: BaseException) -> bool:
        if isinstance(
            error,
            (
                smtplib.SMTPAuthenticationError,
                smtplib.SMTPSenderRefused,
                smtplib.SMTPRecipientsRefused,
                smtplib.SMTPNotSupportedError,
            ),
        ):
            return False
        if isinstance(
            error,
            (
                TimeoutError,
                OSError,
                smtplib.SMTPServerDisconnected,
                smtplib.SMTPConnectError,
            ),
        ):
            return True
        if isinstance(error, smtplib.SMTPResponseException):
            return 400 <= error.smtp_code < 500
        return False

    def _deliver(self, message: EmailMessage) -> None:
        for attempt in range(1, self._max_attempts + 1):
            try:
                self._send_once(message)
                return
            except Exception as error:
                retry = self._is_transient(error) and attempt < self._max_attempts
                if not retry:
                    smtp_code = (
                        error.smtp_code
                        if isinstance(error, smtplib.SMTPResponseException)
                        else None
                    )
                    logger.error(
                        "SMTP delivery failed after %s attempt(s) "
                        "(error_type=%s, smtp_code=%s)",
                        attempt,
                        type(error).__name__,
                        smtp_code,
                    )
                    raise EmailDeliveryError("SMTP delivery failed") from None
                logger.warning(
                    "Transient SMTP delivery failure; retrying attempt %s of %s",
                    attempt + 1,
                    self._max_attempts,
                )
                if self._retry_delay_seconds:
                    time.sleep(self._retry_delay_seconds)

    def send_verification_email(
        self,
        *,
        recipient: str,
        token: str,
        expires_at: datetime,
    ) -> None:
        link = _action_url(self._verification_base_url, token)
        self._deliver(
            self._message(
                recipient=recipient,
                subject="Verify your ICMS email",
                body=(
                    "Verify your ICMS email by opening this secure, single-use link:\n\n"
                    f"{link}\n\n"
                    f"This link expires at {expires_at.isoformat()}. "
                    "If you did not create this account, ignore this message."
                ),
            )
        )

    def send_invitation_email(
        self,
        *,
        recipient: str,
        token: str,
        expires_at: datetime,
        farm_name: str,
    ) -> None:
        link = _action_url(self._invitation_accept_base_url, token)
        self._deliver(
            self._message(
                recipient=recipient,
                subject="You were invited to an ICMS farm",
                body=(
                    f"You were invited to join {farm_name} in ICMS.\n\n"
                    f"Open the secure, single-use invitation link:\n\n{link}\n\n"
                    f"This invitation expires at {expires_at.isoformat()}. "
                    "If you do not recognize this invitation, ignore this message."
                ),
            )
        )

    def send_password_reset_email(
        self,
        *,
        recipient: str,
        token: str,
        expires_at: datetime,
    ) -> None:
        link = _action_url(self._password_reset_base_url, token)
        self._deliver(
            self._message(
                recipient=recipient,
                subject="Reset your ICMS password",
                body=(
                    "Reset your ICMS password with this secure, single-use link:\n\n"
                    f"{link}\n\n"
                    f"This link expires at {expires_at.isoformat()}. "
                    "If you did not request a reset, ignore this message."
                ),
            )
        )


@lru_cache(maxsize=1)
def get_email_sender() -> EmailSender:
    settings = get_settings()
    environment = settings.APP_ENV.strip().lower()
    mode = settings.EMAIL_DELIVERY_MODE

    if mode == "console" and environment in {"development", "local"}:
        return DevelopmentConsoleEmailSender(
            settings.verification_action_url,
            settings.password_reset_action_url,
            settings.invitation_accept_action_url,
        )

    if mode == "smtp":
        password = (
            settings.SMTP_PASSWORD.get_secret_value()
            if settings.SMTP_PASSWORD
            else None
        )
        return SMTPEmailSender(
            host=settings.SMTP_HOST or "",
            port=settings.SMTP_PORT,
            username=settings.SMTP_USERNAME,
            password=password,
            use_starttls=settings.SMTP_USE_STARTTLS,
            use_ssl=settings.SMTP_USE_SSL,
            sender_email=settings.SMTP_SENDER_EMAIL or "",
            sender_name=settings.SMTP_SENDER_NAME,
            verification_base_url=settings.verification_action_url,
            password_reset_base_url=settings.password_reset_action_url,
            invitation_accept_base_url=settings.invitation_accept_action_url,
            timeout_seconds=settings.SMTP_TIMEOUT_SECONDS,
            max_attempts=settings.SMTP_MAX_ATTEMPTS,
            retry_delay_seconds=settings.SMTP_RETRY_DELAY_SECONDS,
        )

    raise EmailDeliveryNotConfiguredError(
        "Email delivery is not configured for this environment."
    )
