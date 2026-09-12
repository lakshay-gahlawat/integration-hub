"""
GitHub provider.

Demonstrates:
- OAuth 2.0 authorization-code flow (authorize + code-for-token exchange)
- Webhook signature verification (HMAC-SHA256 over the raw request body,
  per https://docs.github.com/webhooks/using-webhooks/validating-webhook-deliveries)
- REST reads (GET /user, GET /user/repos)
- REST writes (POST /gists) as the "create/update external data" flow
- Rate-limit awareness via the X-RateLimit-* response headers
"""
from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timezone
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
from app.integrations.normalized import GitHubRepoSummary
from app.models.enums import ProviderType

logger = get_logger(__name__)

GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_API_BASE = "https://api.github.com"

_TIMEOUT = httpx.Timeout(10.0, connect=5.0)


class GitHubProvider(IntegrationProvider):
    provider_type = ProviderType.GITHUB

    def build_authorization_url(self, state: str) -> str:
        params = {
            "client_id": settings.GITHUB_CLIENT_ID,
            "redirect_uri": settings.GITHUB_OAUTH_REDIRECT_URI,
            "scope": "repo gist read:user",
            "state": state,
        }
        query = "&".join(f"{k}={httpx.QueryParams({k: v})[k]}" for k, v in params.items())
        return f"{GITHUB_AUTHORIZE_URL}?{query}"

    async def exchange_code_for_token(self, code: str) -> OAuthTokenResult:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            token_resp = await client.post(
                GITHUB_TOKEN_URL,
                headers={"Accept": "application/json"},
                data={
                    "client_id": settings.GITHUB_CLIENT_ID,
                    "client_secret": settings.GITHUB_CLIENT_SECRET,
                    "code": code,
                    "redirect_uri": settings.GITHUB_OAUTH_REDIRECT_URI,
                },
            )
            _raise_for_provider_error(token_resp, "GitHub token exchange")
            token_data = token_resp.json()
            access_token = token_data.get("access_token")
            if not access_token:
                raise ProviderAPIError(
                    f"GitHub did not return an access token: {token_data}", retryable=False
                )

            user_resp = await client.get(
                f"{GITHUB_API_BASE}/user",
                headers=_auth_headers(access_token),
            )
            _raise_for_provider_error(user_resp, "GitHub user lookup")
            user_data = user_resp.json()

        return OAuthTokenResult(
            access_token=access_token,
            refresh_token=None,  # classic GitHub OAuth apps issue non-expiring tokens
            expires_at=None,
            external_account_id=str(user_data["id"]),
            external_account_name=user_data.get("login", "unknown"),
        )

    async def fetch_account_identity(self, access_token: str) -> tuple[str, str]:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(f"{GITHUB_API_BASE}/user", headers=_auth_headers(access_token))
        _raise_for_provider_error(resp, "GitHub user lookup")
        data = resp.json()
        return str(data["id"]), data.get("login", "unknown")

    def verify_webhook(self, headers: dict[str, str], raw_body: bytes) -> None:
        signature = headers.get("x-hub-signature-256")
        if not signature:
            raise WebhookVerificationError("Missing X-Hub-Signature-256 header")

        if not settings.GITHUB_WEBHOOK_SECRET:
            # No secret configured (e.g. local dev without a public URL for
            # GitHub to call back to). We fail closed rather than silently
            # accepting unverified payloads.
            raise WebhookVerificationError(
                "GITHUB_WEBHOOK_SECRET is not configured; refusing to trust unverified webhook"
            )

        expected = "sha256=" + hmac.new(
            settings.GITHUB_WEBHOOK_SECRET.encode(), raw_body, hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(expected, signature):
            raise WebhookVerificationError("GitHub webhook signature mismatch")

    def parse_webhook(self, headers: dict[str, str], payload: dict[str, Any]) -> ParsedWebhookEvent:
        delivery_id = headers.get("x-github-delivery")
        event_type = headers.get("x-github-event", "unknown")
        if not delivery_id:
            raise WebhookVerificationError("Missing X-GitHub-Delivery header")

        external_account_id = None
        repo_owner = payload.get("repository", {}).get("owner", {})
        if repo_owner:
            external_account_id = str(repo_owner.get("id")) if repo_owner.get("id") else None

        return ParsedWebhookEvent(
            external_event_id=delivery_id,
            event_type=event_type,
            payload=payload,
            external_account_id=external_account_id,
        )

    async def run_sync(self, access_token: str) -> dict[str, Any]:
        """External API -> fetch -> validate/normalize -> downstream
        action -> record result.

        1. fetch:      GET /user/repos
        2. normalize:  parse each entry into GitHubRepoSummary, skipping
                        (and logging) any that don't match the expected
                        shape instead of letting one bad entry fail the
                        whole sync
        3. downstream: create a private Gist recording the normalized
                        result (the "write" half of the integration)
        4. record:     return the normalized summary; the caller persists
                        it on the SyncJob row and writes an audit log entry
        """
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            repos_resp = await client.get(
                f"{GITHUB_API_BASE}/user/repos",
                headers=_auth_headers(access_token),
                params={"per_page": 10, "sort": "updated"},
            )
            _raise_for_provider_error(repos_resp, "GitHub list repos")
            raw_repos = repos_resp.json()
            _log_rate_limit("github", repos_resp.headers)

            normalized_repos: list[GitHubRepoSummary] = []
            for raw in raw_repos:
                try:
                    normalized_repos.append(GitHubRepoSummary.model_validate(raw))
                except ValidationError as exc:
                    logger.warning(
                        f"Skipping malformed GitHub repo entry "
                        f"({raw.get('full_name', 'unknown')}): {exc}"
                    )

            # Demonstration "write" call: record the sync result as a
            # private Gist rather than mutating any of the user's real
            # repositories, which would be an unwelcome side effect of
            # running a portfolio demo against a real account.
            gist_resp = await client.post(
                f"{GITHUB_API_BASE}/gists",
                headers=_auth_headers(access_token),
                json={
                    "description": "Integration Hub sync log",
                    "public": False,
                    "files": {
                        "integration-hub-sync.json": {
                            "content": json.dumps(
                                {
                                    "synced_at": datetime.now(timezone.utc).isoformat(),
                                    "repo_count": len(normalized_repos),
                                    "repos": [r.full_name for r in normalized_repos],
                                },
                                indent=2,
                            )
                        }
                    },
                },
            )
            _raise_for_provider_error(gist_resp, "GitHub create gist")
            gist_url = gist_resp.json().get("html_url")

        return {
            "repo_count": len(normalized_repos),
            "repos": [r.full_name for r in normalized_repos],
            "skipped_invalid_entries": len(raw_repos) - len(normalized_repos),
            "sync_log_gist_url": gist_url,
        }


def _auth_headers(access_token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _raise_for_provider_error(response: httpx.Response, context: str) -> None:
    if response.status_code == 401:
        raise ProviderAPIError(f"{context}: unauthorized (token may be revoked)", status_code=401, retryable=False)
    if response.status_code == 403 and "rate limit" in response.text.lower():
        raise ProviderAPIError(f"{context}: rate limited", status_code=403, retryable=True)
    if response.status_code == 404:
        raise ProviderAPIError(f"{context}: not found", status_code=404, retryable=False)
    if response.status_code >= 500:
        raise ProviderAPIError(f"{context}: upstream server error", status_code=response.status_code, retryable=True)
    if response.status_code >= 400:
        raise ProviderAPIError(
            f"{context}: request failed ({response.status_code}): {response.text[:300]}",
            status_code=response.status_code,
            retryable=False,
        )


def _log_rate_limit(provider: str, headers: httpx.Headers) -> None:
    remaining = headers.get("x-ratelimit-remaining")
    if remaining is not None and int(remaining) < 5:
        logger.warning(f"{provider} API rate limit nearly exhausted: {remaining} requests remaining")
