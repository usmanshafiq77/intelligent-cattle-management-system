import logging
from datetime import datetime
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


class EmailDeliveryNotConfiguredError(RuntimeError):
    pass


def _mask_email(email: str) -> str:
    local, separator, domain = email.partition("@")
    if not separator:
        return "<invalid-email>"
    visible = local[:1] if local else "*"
    return f"{visible}***@{domain}"


class DevelopmentConsoleEmailSender:
    """Local-only delivery that prints a one-time link to server logs."""

    def __init__(self, base_url: str) -> None:
        self._base_url = base_url

    def send_verification_email(
        self,
        *,
        recipient: str,
        token: str,
        expires_at: datetime,
    ) -> None:
        query = urlencode({"token": token})
        separator = "&" if "?" in self._base_url else "?"
        verification_url = f"{self._base_url}{separator}{query}"
        logger.warning(
            "LOCAL DEVELOPMENT ONLY: verification link for %s "
            "(expires %s): %s",
            _mask_email(recipient),
            expires_at.isoformat(),
            verification_url,
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
            "LOCAL DEVELOPMENT ONLY: invitation token for %s to farm %s "
            "(expires %s): %s",
            _mask_email(recipient),
            farm_name,
            expires_at.isoformat(),
            token,
        )


@lru_cache(maxsize=1)
def get_email_sender() -> EmailSender:
    settings = get_settings()
    environment = settings.APP_ENV.strip().lower()
    mode = settings.EMAIL_DELIVERY_MODE.strip().lower()

    if mode == "console" and environment in {
        "development",
        "local",
    }:
        return DevelopmentConsoleEmailSender(
            settings.EMAIL_VERIFICATION_BASE_URL
        )

    raise EmailDeliveryNotConfiguredError(
        "A production email sender is not configured. Console delivery "
        "is restricted to local development."
    )
