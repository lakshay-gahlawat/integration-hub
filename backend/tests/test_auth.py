import uuid


def test_register_creates_user_and_returns_tokens(client):
    email = f"user-{uuid.uuid4().hex[:8]}@example.com"
    resp = client.post(
        "/api/auth/register",
        json={"email": email, "password": "correct-horse-battery-staple", "full_name": "Ada Lovelace"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["user"]["email"] == email
    assert "access_token" in body
    assert "refresh_token" in body


def test_register_duplicate_email_rejected(client):
    email = f"user-{uuid.uuid4().hex[:8]}@example.com"
    payload = {"email": email, "password": "correct-horse-battery-staple", "full_name": "Ada"}
    first = client.post("/api/auth/register", json=payload)
    assert first.status_code == 201

    second = client.post("/api/auth/register", json=payload)
    assert second.status_code == 409


def test_login_with_wrong_password_rejected(client, registered_user):
    resp = client.post(
        "/api/auth/login",
        json={"email": registered_user["user"]["email"], "password": "wrong-password"},
    )
    assert resp.status_code == 401


def test_login_success(client, registered_user):
    resp = client.post(
        "/api/auth/login",
        json={
            "email": registered_user["user"]["email"],
            "password": "correct-horse-battery-staple",
        },
    )
    assert resp.status_code == 200
    assert "access_token" in resp.json()


def test_protected_route_requires_auth(client):
    resp = client.get("/api/auth/me")
    assert resp.status_code in (401, 403)


def test_protected_route_with_valid_token(client, auth_headers):
    resp = client.get("/api/auth/me", headers=auth_headers)
    assert resp.status_code == 200


def test_refresh_rejects_access_token(client, registered_user):
    # An access token must not be usable at the refresh endpoint.
    resp = client.post(
        "/api/auth/refresh", json={"refresh_token": registered_user["access_token"]}
    )
    assert resp.status_code == 401


def test_refresh_issues_new_access_token(client, registered_user):
    resp = client.post(
        "/api/auth/refresh", json={"refresh_token": registered_user["refresh_token"]}
    )
    assert resp.status_code == 200
    assert "access_token" in resp.json()


def test_refresh_rotates_and_invalidates_old_refresh_token(client, registered_user):
    """The refresh token used to obtain a new pair must not work a second
    time -- that's the whole point of rotation."""
    first = client.post(
        "/api/auth/refresh", json={"refresh_token": registered_user["refresh_token"]}
    )
    assert first.status_code == 200
    new_refresh_token = first.json()["refresh_token"]
    assert new_refresh_token != registered_user["refresh_token"]

    reuse_attempt = client.post(
        "/api/auth/refresh", json={"refresh_token": registered_user["refresh_token"]}
    )
    assert reuse_attempt.status_code == 401

    # The newly-issued refresh token, however, still works.
    second = client.post("/api/auth/refresh", json={"refresh_token": new_refresh_token})
    assert second.status_code == 200


def test_logout_revokes_refresh_token(client, registered_user):
    logout_resp = client.post(
        "/api/auth/logout", json={"refresh_token": registered_user["refresh_token"]}
    )
    assert logout_resp.status_code == 204

    refresh_resp = client.post(
        "/api/auth/refresh", json={"refresh_token": registered_user["refresh_token"]}
    )
    assert refresh_resp.status_code == 401


def test_logout_with_already_invalid_token_does_not_error(client):
    resp = client.post("/api/auth/logout", json={"refresh_token": "not-a-real-token"})
    assert resp.status_code == 204
