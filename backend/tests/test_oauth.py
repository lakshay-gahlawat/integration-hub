"""
Tests the Redis-backed OAuth state mechanism: issuing state via
/oauth/start, and validating it on /oauth/callback without relying on the
callback carrying an Authorization header (it can't -- see
app/services/oauth_state_service.py for why).
"""
import pytest

from app.integrations.base import OAuthTokenResult
from app.integrations.github_provider import GitHubProvider


@pytest.fixture()
def mock_github_token_exchange(monkeypatch):
    async def fake_exchange(self, code: str):
        return OAuthTokenResult(
            access_token=f"gh-access-for-{code}",
            refresh_token=None,
            expires_at=None,
            external_account_id="1001",
            external_account_name="octocat",
        )

    monkeypatch.setattr(GitHubProvider, "exchange_code_for_token", fake_exchange)


def test_oauth_start_returns_state_and_authorization_url(client, auth_headers):
    resp = client.get("/api/integrations/github/oauth/start", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["state"]
    assert "github.com/login/oauth/authorize" in body["authorization_url"]
    assert body["state"] in body["authorization_url"]


def test_oauth_callback_with_valid_state_completes_connection(
    client, auth_headers, mock_github_token_exchange
):
    start_resp = client.get("/api/integrations/github/oauth/start", headers=auth_headers)
    state = start_resp.json()["state"]

    # No Authorization header here on purpose -- the callback must not
    # depend on it.
    callback_resp = client.get(
        f"/api/integrations/github/oauth/callback?code=abc123&state={state}"
    )
    assert callback_resp.status_code == 200
    body = callback_resp.json()
    assert body["provider"] == "github"
    assert body["status"] == "connected"
    assert body["external_account_id"] == "1001"

    # And it landed on the correct user's account.
    integrations_resp = client.get("/api/integrations", headers=auth_headers)
    assert any(i["external_account_id"] == "1001" for i in integrations_resp.json())


def test_oauth_callback_with_invalid_state_is_rejected(client, mock_github_token_exchange):
    resp = client.get("/api/integrations/github/oauth/callback?code=abc123&state=not-a-real-state")
    assert resp.status_code == 401


def test_oauth_callback_with_reused_state_is_rejected(client, auth_headers, mock_github_token_exchange):
    start_resp = client.get("/api/integrations/github/oauth/start", headers=auth_headers)
    state = start_resp.json()["state"]

    first = client.get(f"/api/integrations/github/oauth/callback?code=abc123&state={state}")
    assert first.status_code == 200

    second = client.get(f"/api/integrations/github/oauth/callback?code=abc123&state={state}")
    assert second.status_code == 401


def test_oauth_callback_with_expired_state_is_rejected(client, auth_headers, mock_github_token_exchange):
    """We don't want to sleep 10 real minutes in a test -- instead, delete
    the state key directly to simulate TTL expiry, which is exactly what
    Redis does when the TTL elapses (GETDEL returns nil either way)."""
    from app.core.redis_client import get_redis

    start_resp = client.get("/api/integrations/github/oauth/start", headers=auth_headers)
    state = start_resp.json()["state"]

    get_redis().delete(f"oauth_state:{state}")

    resp = client.get(f"/api/integrations/github/oauth/callback?code=abc123&state={state}")
    assert resp.status_code == 401


def test_oauth_callback_with_wrong_provider_is_rejected(client, auth_headers, mock_github_token_exchange):
    """A state issued for GitHub must not be usable to complete a Slack
    callback -- otherwise the provider check in the callback URL would be
    purely decorative."""
    start_resp = client.get("/api/integrations/github/oauth/start", headers=auth_headers)
    state = start_resp.json()["state"]

    resp = client.get(f"/api/integrations/slack/oauth/callback?code=abc123&state={state}")
    assert resp.status_code == 401


def test_oauth_start_requires_auth(client):
    resp = client.get("/api/integrations/github/oauth/start")
    assert resp.status_code in (401, 403)
