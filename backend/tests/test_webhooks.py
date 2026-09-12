import hashlib
import hmac
import json
import time


GITHUB_SECRET = "github-test-secret"
SLACK_SECRET = "slack-test-secret"


def _github_signature(body: bytes) -> str:
    return "sha256=" + hmac.new(GITHUB_SECRET.encode(), body, hashlib.sha256).hexdigest()


def _slack_signature(body: bytes, timestamp: str) -> str:
    base_string = f"v0:{timestamp}:{body.decode()}".encode()
    return "v0=" + hmac.new(SLACK_SECRET.encode(), base_string, hashlib.sha256).hexdigest()


def _github_payload(delivery_id: str = "delivery-1", owner_id: int = 42):
    body = json.dumps({"action": "opened", "repository": {"owner": {"id": owner_id}}}).encode()
    headers = {
        "X-GitHub-Delivery": delivery_id,
        "X-GitHub-Event": "issues",
        "X-Hub-Signature-256": _github_signature(body),
        "Content-Type": "application/json",
    }
    return body, headers


def test_github_webhook_accepted_with_valid_signature(client):
    body, headers = _github_payload()
    resp = client.post("/api/webhooks/github", content=body, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["accepted"] is True
    assert data["duplicate"] is False


def test_github_webhook_rejected_with_invalid_signature(client):
    body, headers = _github_payload(delivery_id="delivery-bad-sig")
    headers["X-Hub-Signature-256"] = "sha256=deadbeef"
    resp = client.post("/api/webhooks/github", content=body, headers=headers)
    assert resp.status_code == 401


def test_github_webhook_duplicate_delivery_is_deduplicated(client):
    body, headers = _github_payload(delivery_id="delivery-duplicate")
    first = client.post("/api/webhooks/github", content=body, headers=headers)
    assert first.status_code == 200
    assert first.json()["duplicate"] is False

    second = client.post("/api/webhooks/github", content=body, headers=headers)
    assert second.status_code == 200
    assert second.json()["duplicate"] is True


def test_slack_webhook_accepted_with_valid_signature(client):
    body = json.dumps(
        {"event_id": "Ev-1", "team_id": "T123", "event": {"type": "app_mention"}}
    ).encode()
    timestamp = str(int(time.time()))
    headers = {
        "X-Slack-Request-Timestamp": timestamp,
        "X-Slack-Signature": _slack_signature(body, timestamp),
        "Content-Type": "application/json",
    }
    resp = client.post("/api/webhooks/slack", content=body, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["accepted"] is True


def test_slack_webhook_rejected_with_stale_timestamp(client):
    body = json.dumps({"event_id": "Ev-2", "event": {"type": "message"}}).encode()
    stale_timestamp = str(int(time.time()) - 60 * 60)  # 1 hour old
    headers = {
        "X-Slack-Request-Timestamp": stale_timestamp,
        "X-Slack-Signature": _slack_signature(body, stale_timestamp),
    }
    resp = client.post("/api/webhooks/slack", content=body, headers=headers)
    assert resp.status_code == 401


def test_webhook_list_requires_auth(client):
    resp = client.get("/api/webhooks")
    assert resp.status_code in (401, 403)


def test_webhook_list_returns_received_events(client, auth_headers):
    # Connect an integration whose external_account_id matches the
    # webhook payload's repository owner id, so the event links to this
    # user's integration and is visible to them.
    client.post(
        "/api/integrations", headers=auth_headers,
        json={"provider": "github", "access_token": "42"},
    )

    body, headers = _github_payload(delivery_id="delivery-listed")
    client.post("/api/webhooks/github", content=body, headers=headers)

    resp = client.get("/api/webhooks", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert any(e["external_event_id"] == "delivery-listed" for e in data["items"])


def test_concurrent_duplicate_delivery_only_persists_one_row(engine):
    """Exercises the actual concurrency guarantee: two independent DB
    sessions (simulating two webhook requests arriving at nearly the same
    instant) both try to insert the same (provider, external_event_id).
    The application-level pre-check in WebhookService can't catch this --
    both sessions can pass a SELECT before either commits -- so this test
    specifically bypasses that pre-check and calls the repository's
    `create` directly on two separate sessions, proving the UNIQUE
    constraint is what actually prevents the duplicate row."""
    from sqlalchemy.orm import sessionmaker

    from app.models.enums import ProviderType
    from app.repositories.webhook_repo import DuplicateWebhookEvent, WebhookRepository

    SessionFactory = sessionmaker(bind=engine, future=True)
    session_a = SessionFactory()
    session_b = SessionFactory()

    try:
        repo_a = WebhookRepository(session_a)
        repo_b = WebhookRepository(session_b)

        event_kwargs = dict(
            provider=ProviderType.GITHUB,
            external_event_id="race-condition-delivery",
            event_type="push",
            payload={"race": True},
            integration_id=None,
        )

        repo_a.create(**event_kwargs)

        raised = False
        try:
            repo_b.create(**event_kwargs)
        except DuplicateWebhookEvent:
            raised = True
        assert raised, "second concurrent insert should have hit the UNIQUE constraint"
    finally:
        session_a.close()
        session_b.close()
