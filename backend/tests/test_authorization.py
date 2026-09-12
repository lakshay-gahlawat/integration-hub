"""
Verifies that User A can never read User B's webhook events, sync jobs, or
integrations -- via list endpoints (must not appear) or direct-by-ID
endpoints (must 404, not leak existence via a 403 or partial data).
"""
from test_webhooks import _github_payload


def _second_user_headers(client, email="user-b@example.com"):
    resp = client.post(
        "/api/auth/register",
        json={"email": email, "password": "another-strong-pass-2", "full_name": "User B"},
    )
    assert resp.status_code == 201, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _connect_github(client, headers, token="tok-a"):
    resp = client.post(
        "/api/integrations", headers=headers, json={"provider": "github", "access_token": token}
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


class TestCrossUserIntegrationAccess:
    def test_user_a_cannot_get_user_bs_integration(self, client, auth_headers):
        integration = _connect_github(client, auth_headers, token="owner-token")
        other_headers = _second_user_headers(client)

        resp = client.get(f"/api/integrations/{integration['id']}", headers=other_headers)
        assert resp.status_code == 404

    def test_user_a_cannot_disconnect_user_bs_integration(self, client, auth_headers):
        integration = _connect_github(client, auth_headers, token="owner-token-2")
        other_headers = _second_user_headers(client, email="user-b2@example.com")

        resp = client.delete(f"/api/integrations/{integration['id']}", headers=other_headers)
        assert resp.status_code == 404

        # Confirm it's untouched from the real owner's perspective.
        owned = client.get(f"/api/integrations/{integration['id']}", headers=auth_headers)
        assert owned.json()["status"] == "connected"

    def test_user_a_cannot_sync_user_bs_integration(self, client, auth_headers):
        integration = _connect_github(client, auth_headers, token="owner-token-3")
        other_headers = _second_user_headers(client, email="user-b3@example.com")

        resp = client.post(f"/api/integrations/{integration['id']}/sync", headers=other_headers)
        assert resp.status_code == 404

    def test_users_list_endpoint_never_shows_other_users_integrations(self, client, auth_headers):
        _connect_github(client, auth_headers, token="owner-token-4")
        other_headers = _second_user_headers(client, email="user-b4@example.com")

        resp = client.get("/api/integrations", headers=other_headers)
        assert resp.status_code == 200
        assert resp.json() == []


class TestCrossUserWebhookAccess:
    def test_user_a_cannot_list_user_bs_webhook_events(self, client, auth_headers):
        integration = _connect_github(client, auth_headers, token="42")
        body, headers = _github_payload(delivery_id="cross-user-webhook-1")
        client.post("/api/webhooks/github", content=body, headers=headers)

        other_headers = _second_user_headers(client, email="webhook-user-b@example.com")
        resp = client.get("/api/webhooks", headers=other_headers)
        assert resp.status_code == 200
        assert all(e["external_event_id"] != "cross-user-webhook-1" for e in resp.json()["items"])

    def test_user_a_cannot_get_user_bs_webhook_event_by_id(self, client, auth_headers):
        _connect_github(client, auth_headers, token="43")
        body, headers = _github_payload(delivery_id="cross-user-webhook-2", owner_id=43)

        receive_resp = client.post("/api/webhooks/github", content=body, headers=headers)
        assert receive_resp.status_code == 200
        event_id = receive_resp.json()["event_id"]

        other_headers = _second_user_headers(client, email="webhook-user-b2@example.com")
        resp = client.get(f"/api/webhooks/{event_id}", headers=other_headers)
        assert resp.status_code == 404

        # The real owner CAN see it.
        owner_resp = client.get(f"/api/webhooks/{event_id}", headers=auth_headers)
        assert owner_resp.status_code == 200


class TestCrossUserSyncJobAccess:
    def test_user_a_cannot_list_user_bs_sync_jobs(self, client, auth_headers):
        integration = _connect_github(client, auth_headers, token="sync-owner-1")
        sync_resp = client.post(f"/api/integrations/{integration['id']}/sync", headers=auth_headers)
        assert sync_resp.status_code == 202
        job_id = sync_resp.json()["sync_job_id"]

        other_headers = _second_user_headers(client, email="sync-user-b@example.com")
        resp = client.get("/api/sync-jobs", headers=other_headers)
        assert resp.status_code == 200
        assert all(j["id"] != job_id for j in resp.json()["items"])

    def test_user_a_cannot_get_user_bs_sync_job_by_id(self, client, auth_headers):
        integration = _connect_github(client, auth_headers, token="sync-owner-2")
        sync_resp = client.post(f"/api/integrations/{integration['id']}/sync", headers=auth_headers)
        job_id = sync_resp.json()["sync_job_id"]

        other_headers = _second_user_headers(client, email="sync-user-b2@example.com")
        resp = client.get(f"/api/sync-jobs/{job_id}", headers=other_headers)
        assert resp.status_code == 404

        owner_resp = client.get(f"/api/sync-jobs/{job_id}", headers=auth_headers)
        assert owner_resp.status_code == 200
