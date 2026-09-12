def test_list_integrations_empty_initially(client, auth_headers):
    resp = client.get("/api/integrations", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == []


def test_connect_integration_with_manual_token(client, auth_headers):
    resp = client.post(
        "/api/integrations",
        headers=auth_headers,
        json={"provider": "github", "access_token": "ghp_faketoken123"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["provider"] == "github"
    assert body["status"] == "connected"


def test_connect_is_idempotent_per_provider(client, auth_headers):
    """Connecting the same provider twice should update the existing
    integration row rather than creating a second one (enforced by the
    unique constraint on (user_id, provider))."""
    client.post(
        "/api/integrations", headers=auth_headers,
        json={"provider": "slack", "access_token": "xoxb-first"},
    )
    client.post(
        "/api/integrations", headers=auth_headers,
        json={"provider": "slack", "access_token": "xoxb-second"},
    )
    resp = client.get("/api/integrations", headers=auth_headers)
    slack_integrations = [i for i in resp.json() if i["provider"] == "slack"]
    assert len(slack_integrations) == 1


def test_cannot_access_another_users_integration(client, auth_headers):
    connect_resp = client.post(
        "/api/integrations", headers=auth_headers,
        json={"provider": "github", "access_token": "ghp_owner_token"},
    )
    integration_id = connect_resp.json()["id"]

    # Register a second, unrelated user.
    other_register = client.post(
        "/api/auth/register",
        json={"email": "other-user@example.com", "password": "another-strong-pass", "full_name": "Other"},
    )
    other_headers = {"Authorization": f"Bearer {other_register.json()['access_token']}"}

    resp = client.get(f"/api/integrations/{integration_id}", headers=other_headers)
    assert resp.status_code == 404


def test_disconnect_integration(client, auth_headers):
    connect_resp = client.post(
        "/api/integrations", headers=auth_headers,
        json={"provider": "github", "access_token": "ghp_to_disconnect"},
    )
    integration_id = connect_resp.json()["id"]

    resp = client.delete(f"/api/integrations/{integration_id}", headers=auth_headers)
    assert resp.status_code == 204

    get_resp = client.get(f"/api/integrations/{integration_id}", headers=auth_headers)
    assert get_resp.json()["status"] == "disconnected"


def test_trigger_sync_enqueues_job(client, auth_headers):
    connect_resp = client.post(
        "/api/integrations", headers=auth_headers,
        json={"provider": "github", "access_token": "ghp_sync_token"},
    )
    integration_id = connect_resp.json()["id"]

    resp = client.post(f"/api/integrations/{integration_id}/sync", headers=auth_headers)
    assert resp.status_code == 202
    assert "sync_job_id" in resp.json()


def test_trigger_sync_on_disconnected_integration_fails(client, auth_headers):
    connect_resp = client.post(
        "/api/integrations", headers=auth_headers,
        json={"provider": "github", "access_token": "ghp_will_disconnect"},
    )
    integration_id = connect_resp.json()["id"]
    client.delete(f"/api/integrations/{integration_id}", headers=auth_headers)

    resp = client.post(f"/api/integrations/{integration_id}/sync", headers=auth_headers)
    assert resp.status_code == 409
