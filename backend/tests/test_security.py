"""
Security-focused tests: credentials never leak through API responses,
credentials are actually encrypted in the database (not just absent from
the schema), and access/refresh tokens can't be swapped for one another.
"""
from app.core.crypto import decrypt_credential
from app.models.integration import Integration


def test_integration_response_never_includes_access_token(client, auth_headers):
    resp = client.post(
        "/api/integrations", headers=auth_headers,
        json={"provider": "github", "access_token": "super-secret-token-value"},
    )
    assert resp.status_code == 201
    body = resp.json()
    # The two fields that actually hold credentials must be absent
    # entirely -- not just null, not present under another name.
    assert "access_token" not in body
    assert "refresh_token" not in body
    assert set(body.keys()) == {
        "id", "provider", "status", "external_account_id", "external_account_name",
        "last_synced_at", "last_error", "created_at", "updated_at",
    }
    # Note: external_account_id/external_account_name legitimately derive
    # from the token via the (test-mocked) provider identity lookup, the
    # same way a real GitHub username is public-ish account metadata, not
    # a secret -- so we assert on field presence/absence above rather than
    # a blanket "token substring not anywhere in the response" check.


def test_integration_list_response_never_includes_tokens(client, auth_headers):
    client.post(
        "/api/integrations", headers=auth_headers,
        json={"provider": "slack", "access_token": "another-secret-value"},
    )
    resp = client.get("/api/integrations", headers=auth_headers)
    assert resp.status_code == 200
    for integration in resp.json():
        assert "access_token" not in integration
        assert "refresh_token" not in integration


def test_access_token_is_encrypted_at_rest(client, auth_headers, db_session):
    plaintext_token = "plaintext-should-not-appear-in-db"
    resp = client.post(
        "/api/integrations", headers=auth_headers,
        json={"provider": "github", "access_token": plaintext_token},
    )
    integration_id = resp.json()["id"]

    stored = db_session.get(Integration, integration_id)
    assert stored.access_token is not None
    assert stored.access_token != plaintext_token
    assert plaintext_token not in stored.access_token

    # But it decrypts back to the original value when we actually need it
    # for an outbound API call.
    assert decrypt_credential(stored.access_token) == plaintext_token


def test_access_token_cannot_be_used_as_refresh_token(client, registered_user):
    resp = client.post(
        "/api/auth/refresh", json={"refresh_token": registered_user["access_token"]}
    )
    assert resp.status_code == 401


def test_refresh_token_cannot_be_used_as_access_token(client, registered_user):
    resp = client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {registered_user['refresh_token']}"}
    )
    assert resp.status_code == 401


def test_invalid_jwt_is_rejected(client):
    resp = client.get("/api/auth/me", headers={"Authorization": "Bearer not-a-real-jwt"})
    assert resp.status_code == 401


def test_refresh_with_garbage_token_is_rejected(client):
    resp = client.post("/api/auth/refresh", json={"refresh_token": "not-a-real-jwt"})
    assert resp.status_code == 401
