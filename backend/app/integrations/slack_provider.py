"""
Slack provider.

Demonstrates a deliberately different set of integration patterns than
GitHub so the portfolio shows breadth rather than repeating the same
pattern twice:
- OAuth 2.0 (Slack's v2 "OAuth & Permissions" flow, JSON token response
  instead of GitHub's form-encoded one)
- Webhook signature verification using Slack's v0 signing-secret scheme,
  which signs a composed base string (version + timestamp + body) instead
  of just the raw body like GitHub does
- Event deduplication using Slack's own event_id (Slack redelivers events
  that aren't acknowledged within 3 seconds, which is a realistic
  at-least-once delivery scenario for the idempotency layer to handle)
- REST reads (conversations.list) and writes (chat.postMessage)
"""
from __future__ import annotations

import hashlib
import hmac
import time
from typing import Any

import httpx
from pydantic import ValidationError

from app.core.config import settings
from app.core.logging import get_logger
from app.integrations.base import (
    IntegrationProvider,
    OAuthTokenResult,
    ParsedWebhookEvent,
    ProviderAPIError,
    WebhookVerificationError,
)
from app.integrations.normalized import SlackChannelSummary
from app.models.enums import ProviderType

logger = get_logger(__name__)

SLACK_AUTHORIZE_URL = "https://slack.com/oauth/v2/authorize"
SLACK_TOKEN_URL = "https://slack.com/api/oauth.v2.access"
SLACK_API_BASE = "https://slack.com/api"

_TIMEOUT = httpx.Timeout(10.0, connect=5.0)
# Slack recommends rejecting requests older than 5 minutes to prevent replay
# attacks using a captured signature.
_MAX_SIGNATURE_AGE_SECONDS = 60 * 5


class SlackProvider(IntegrationProvider):
    provider_type = ProviderType.SLACK

    def build_authorization_url(self, state: str) -> str:
        params = httpx.QueryParams(
            {
                "client_id": settings.SLACK_CLIENT_ID,
                "scope": "channels:read,chat:write",
                "redirect_uri": settings.SLACK_OAUTH_REDIRECT_URI,
                "state": state,
            }
        )
        return f"{SLACK_AUTHORIZE_URL}?{params}"

    async def exchange_code_for_token(self, code: str) -> OAuthTokenResult:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                SLACK_TOKEN_URL,
                data={
                    "client_id": settings.SLACK_CLIENT_ID,
                    "client_secret": settings.SLACK_CLIENT_SECRET,
                    "code": code,
                    "redirect_uri": settings.SLACK_OAUTH_REDIRECT_URI,
                },
            )
        _raise_for_provider_error(resp, "Slack token exchange")
        data = resp.json()
        if not data.get("ok"):
            raise ProviderAPIError(f"Slack token exchange failed: {data.get('error')}", retryable=False)

        access_token = data["access_token"]
        team = data.get("team", {})

        return OAuthTokenResult(
            access_token=access_token,
            refresh_token=None,  # Slack bot tokens don't expire under the classic flow used here
            expires_at=None,
            external_account_id=team.get("id", "unknown"),
            external_account_name=team.get("name", "unknown"),
        )

    async def fetch_account_identity(self, access_token: str) -> tuple[str, str]:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                f"{SLACK_API_BASE}/auth.test", headers={"Authorization": f"Bearer {access_token}"}
            )
        _raise_for_provider_error(resp, "Slack auth.test")
        data = resp.json()
        if not data.get("ok"):
            raise ProviderAPIError(f"Slack auth.test failed: {data.get('error')}", retryable=False)
        return data.get("team_id", "unknown"), data.get("team", "unknown")

    def verify_webhook(self, headers: dict[str, str], raw_body: bytes) -> None:
        timestamp = headers.get("x-slack-request-timestamp")
        signature = headers.get("x-slack-signature")
        if not timestamp or not signature:
            raise WebhookVerificationError("Missing Slack signature headers")

        if abs(time.time() - int(timestamp)) > _MAX_SIGNATURE_AGE_SECONDS:
            raise WebhookVerificationError("Slack webhook timestamp too old (possible replay)")

        if not settings.SLACK_SIGNING_SECRET:
            raise WebhookVerificationError(
                "SLACK_SIGNING_SECRET is not configured; refusing to trust unverified webhook"
            )

        base_string = f"v0:{timestamp}:{raw_body.decode('utf-8')}"
        expected = "v0=" + hmac.new(
            settings.SLACK_SIGNING_SECRET.encode(), base_string.encode(), hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(expected, signature):
            raise WebhookVerificationError("Slack webhook signature mismatch")

    def parse_webhook(self, headers: dict[str, str], payload: dict[str, Any]) -> ParsedWebhookEvent:
        # Slack wraps the actual event in an "event" key and provides its
        # own event_id used as the idempotency key.
        event_id = payload.get("event_id")
        if not event_id:
            raise WebhookVerificationError("Missing Slack event_id in payload")

        inner_event = payload.get("event", {})
        event_type = inner_event.get("type", payload.get("type", "unknown"))

        return ParsedWebhookEvent(
            external_event_id=event_id,
            event_type=event_type,
            payload=payload,
            external_account_id=payload.get("team_id"),
        )

    async def run_sync(self, access_token: str) -> dict[str, Any]:
        """External API -> fetch -> validate/normalize -> downstream
        action -> record result.

        1. fetch:      conversations.list
        2. normalize:  parse each entry into SlackChannelSummary, skipping
                        (and logging) anything that doesn't match the
                        expected shape
        3. downstream: post a summary message to the first channel found
                        (the "write" half of the integration)
        4. record:     return the normalized summary; the caller persists
                        it on the SyncJob row and writes an audit log entry
        """
        headers = {"Authorization": f"Bearer {access_token}"}
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            channels_resp = await client.get(
                f"{SLACK_API_BASE}/conversations.list",
                headers=headers,
                params={"limit": 20, "types": "public_channel"},
            )
            _raise_for_provider_error(channels_resp, "Slack list channels")
            channels_data = channels_resp.json()
            if not channels_data.get("ok"):
                raise ProviderAPIError(
                    f"Slack list channels failed: {channels_data.get('error')}",
                    retryable=_is_retryable_slack_error(channels_data.get("error")),
                )
            raw_channels = channels_data.get("channels", [])

            normalized_channels: list[SlackChannelSummary] = []
            for raw in raw_channels:
                try:
                    normalized_channels.append(SlackChannelSummary.model_validate(raw))
                except ValidationError as exc:
                    logger.warning(
                        f"Skipping malformed Slack channel entry "
                        f"({raw.get('name', 'unknown')}): {exc}"
                    )

            post_result: dict[str, Any] = {"posted": False, "reason": None}
            if normalized_channels:
                target = normalized_channels[0]
                post_resp = await client.post(
                    f"{SLACK_API_BASE}/chat.postMessage",
                    headers=headers,
                    json={
                        "channel": target.id,
                        "text": "Integration Hub sync completed: "
                        f"found {len(normalized_channels)} channel(s).",
                    },
                )
                _raise_for_provider_error(post_resp, "Slack post message")
                post_data = post_resp.json()
                if post_data.get("ok"):
                    post_result = {"posted": True, "channel": target.name}
                else:
                    # Not fatal for the sync as a whole -- most commonly the
                    # bot simply hasn't been invited to the channel yet.
                    post_result = {"posted": False, "reason": post_data.get("error")}

        return {
            "channel_count": len(normalized_channels),
            "channels": [c.name for c in normalized_channels],
            "skipped_invalid_entries": len(raw_channels) - len(normalized_channels),
            "demo_message": post_result,
        }


def _is_retryable_slack_error(error: str | None) -> bool:
    return error in {"ratelimited", "internal_error", "service_unavailable"}


def _raise_for_provider_error(response: httpx.Response, context: str) -> None:
    if response.status_code == 429:
        raise ProviderAPIError(f"{context}: rate limited", status_code=429, retryable=True)
    if response.status_code == 401:
        raise ProviderAPIError(f"{context}: unauthorized", status_code=401, retryable=False)
    if response.status_code >= 500:
        raise ProviderAPIError(f"{context}: upstream server error", status_code=response.status_code, retryable=True)
    if response.status_code >= 400:
        raise ProviderAPIError(
            f"{context}: request failed ({response.status_code}): {response.text[:300]}",
            status_code=response.status_code,
            retryable=False,
        )
