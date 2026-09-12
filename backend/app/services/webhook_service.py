import json
from typing import Any

from sqlalchemy.orm import Session

from app.integrations.base import WebhookVerificationError
from app.integrations.registry import get_provider
from app.models.enums import ProviderType
from app.models.webhook_event import WebhookEvent
from app.repositories.audit_repo import AuditRepository
from app.repositories.integration_repo import IntegrationRepository
from app.repositories.webhook_repo import DuplicateWebhookEvent, WebhookRepository
from app.workers.tasks import process_webhook_event


class WebhookService:
    """
    Implements the pipeline described in the README:

        POST /webhooks/{provider}
              -> verify signature
              -> parse + validate payload
              -> check duplicate (idempotency)
              -> persist event
              -> enqueue background processing job
              -> return 200 immediately

    Everything after "persist event" happens in a Celery task
    (process_webhook_event) so that a slow downstream side effect never
    causes the webhook HTTP response to time out -- providers like GitHub
    and Slack will disable a webhook endpoint that repeatedly responds
    slowly or with 5xx.
    """

    def __init__(self, db: Session):
        self.db = db
        self.webhooks = WebhookRepository(db)
        self.integrations = IntegrationRepository(db)
        self.audit = AuditRepository(db)

    def receive(
        self, *, provider: ProviderType, headers: dict[str, str], raw_body: bytes
    ) -> tuple[WebhookEvent | None, bool]:
        """Returns (event, is_duplicate). Raises WebhookVerificationError on
        an invalid signature -- the router translates that to HTTP 401."""
        provider_impl = get_provider(provider)
        provider_impl.verify_webhook(headers, raw_body)

        try:
            payload: dict[str, Any] = json.loads(raw_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise WebhookVerificationError(f"Invalid JSON payload: {exc}") from exc

        parsed = provider_impl.parse_webhook(headers, payload)

        integration = None
        if parsed.external_account_id:
            integration = self.integrations.find_by_external_account(
                provider, parsed.external_account_id
            )

        if self.webhooks.exists(provider, parsed.external_event_id):
            return None, True

        try:
            event = self.webhooks.create(
                provider=provider,
                external_event_id=parsed.external_event_id,
                event_type=parsed.event_type,
                payload=parsed.payload,
                integration_id=integration.id if integration else None,
            )
        except DuplicateWebhookEvent:
            # Lost the race against a concurrent identical delivery -- the
            # DB unique constraint caught what the pre-check missed.
            return None, True

        self.audit.record(
            action="webhook.received",
            user_id=integration.user_id if integration else None,
            integration_id=integration.id if integration else None,
            details={"provider": provider.value, "event_type": parsed.event_type, "event_id": str(event.id)},
        )

        process_webhook_event.delay(str(event.id))
        return event, False
