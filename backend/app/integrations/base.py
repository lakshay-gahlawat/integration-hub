"""
IntegrationProvider is the abstraction the rest of the application codes
against. Nothing outside app/integrations/ should know that "github" means
HMAC-SHA256 signatures and "slack" means a different header/algorithm, or
that GitHub's OAuth token exchange returns form-encoded data while Slack's
returns JSON. Adding a third provider means writing one new class here and
registering it in `registry.py` -- no changes to routers, services, or the
webhook pipeline are required.
"""
from __future__ import annotations

import abc
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.models.enums import ProviderType


class ProviderAPIError(Exception):
    """Raised when the external provider's API returns an error response
    that the caller should treat as a failure (used to trigger the retry /
    backoff machinery in the workers layer)."""

    def __init__(self, message: str, *, status_code: int | None = None, retryable: bool = True):
        super().__init__(message)
        self.status_code = status_code
        self.retryable = retryable


class WebhookVerificationError(Exception):
    """Raised when a webhook's signature does not match, or required
    headers are missing. Callers must return HTTP 401/400 and must NOT
    process the payload."""


@dataclass
class OAuthTokenResult:
    access_token: str
    refresh_token: str | None
    expires_at: datetime | None
    external_account_id: str
    external_account_name: str


@dataclass
class ParsedWebhookEvent:
    external_event_id: str
    event_type: str
    payload: dict[str, Any]
    external_account_id: str | None = None


class IntegrationProvider(abc.ABC):
    """Base class every concrete provider (GitHub, Slack, ...) implements."""

    provider_type: ProviderType

    # ---- OAuth ----
    @abc.abstractmethod
    def build_authorization_url(self, state: str) -> str:
        ...

    @abc.abstractmethod
    async def exchange_code_for_token(self, code: str) -> OAuthTokenResult:
        ...

    @abc.abstractmethod
    async def fetch_account_identity(self, access_token: str) -> tuple[str, str]:
        """Returns (external_account_id, external_account_name) for the
        given token. Used both by the OAuth flow (to record who connected)
        and by the manual-token connection path, so a pasted personal
        access token gets the same external_account_id linkage that OAuth
        would have produced -- without it, inbound webhooks could never be
        matched back to a manually-connected integration."""
        ...

    # ---- Webhooks ----
    @abc.abstractmethod
    def verify_webhook(self, headers: dict[str, str], raw_body: bytes) -> None:
        """Raise WebhookVerificationError if the signature is invalid."""
        ...

    @abc.abstractmethod
    def parse_webhook(self, headers: dict[str, str], payload: dict[str, Any]) -> ParsedWebhookEvent:
        ...

    # ---- Data sync ----
    @abc.abstractmethod
    async def run_sync(self, access_token: str) -> dict[str, Any]:
        """Perform the provider's read (+ demonstration write) flow and
        return a small JSON-serializable summary stored on the SyncJob."""
        ...
