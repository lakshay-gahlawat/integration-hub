"""
Celery tasks. Each task opens its own DB session (SessionLocal) because it
runs in a separate worker process with no access to a FastAPI request's
dependency-injected session.

Retry policy: transient failures (network errors, 5xx, provider rate
limits) are retried with exponential backoff up to MAX_RETRIES times.
Permanent failures (401 unauthorized / revoked token, 404, malformed
payloads) are NOT retried -- retrying those would just hammer the
provider's API for no benefit and could get the integration flagged for
abuse. This distinction is carried end-to-end via
`ProviderAPIError.retryable`.
"""
import asyncio

from celery.utils.log import get_task_logger

from app.core.celery_app import celery_app
from app.db.session import SessionLocal
from app.integrations.base import ProviderAPIError
from app.models.enums import SyncTrigger
from app.repositories.audit_repo import AuditRepository
from app.repositories.integration_repo import IntegrationRepository
from app.repositories.sync_job_repo import SyncJobRepository
from app.repositories.webhook_repo import WebhookRepository

logger = get_task_logger(__name__)

MAX_RETRIES = 5
BASE_BACKOFF_SECONDS = 10

# Webhook event types that should trigger a downstream sync. Kept as data
# rather than branching provider-specific code throughout the task, so
# extending this list later is a one-line change.
_SYNC_TRIGGERING_EVENT_TYPES = {"push", "repository", "app_mention", "message"}


def _run_async(coro):
    """Celery tasks are synchronous; our provider clients are async
    (httpx.AsyncClient). Each task call gets its own event loop."""
    return asyncio.run(coro)


@celery_app.task(bind=True, max_retries=MAX_RETRIES, name="run_integration_sync")
def run_integration_sync(self, job_id: str):
    from app.services.sync_service import execute_sync_job  # local import avoids a circular import

    db = SessionLocal()
    try:
        sync_jobs = SyncJobRepository(db)
        job = sync_jobs.get(job_id)
        if job is None:
            logger.error(f"Sync job {job_id} not found; nothing to do")
            return

        try:
            _run_async(execute_sync_job(db, job))
        except ProviderAPIError as exc:
            if exc.retryable and self.request.retries < MAX_RETRIES:
                backoff = BASE_BACKOFF_SECONDS * (2 ** self.request.retries)
                sync_jobs.mark_retrying(job, str(exc))
                logger.warning(
                    f"Sync job {job_id} failed (retryable), retrying in {backoff}s "
                    f"(attempt {self.request.retries + 1}/{MAX_RETRIES})"
                )
                raise self.retry(exc=exc, countdown=backoff)
            sync_jobs.mark_failed(job, str(exc))
            logger.error(f"Sync job {job_id} failed permanently: {exc}")
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=MAX_RETRIES, name="process_webhook_event")
def process_webhook_event(self, event_id: str):
    db = SessionLocal()
    try:
        webhooks = WebhookRepository(db)
        integrations = IntegrationRepository(db)
        sync_jobs = SyncJobRepository(db)
        audit = AuditRepository(db)

        event = webhooks.get(event_id)
        if event is None:
            logger.error(f"Webhook event {event_id} not found; nothing to do")
            return

        webhooks.mark_processing(event)

        try:
            # Processing here means: interpret the event and decide whether
            # it warrants pulling fresh data from the provider. A more
            # elaborate system might apply the event's diff directly; for
            # this portfolio scope, triggering a scoped sync is the
            # realistic, demonstrable behavior.
            if event.integration_id and event.event_type in _SYNC_TRIGGERING_EVENT_TYPES:
                integration = integrations.get(event.integration_id)
                if integration and integration.access_token:
                    job = sync_jobs.create(
                        integration_id=integration.id, trigger=SyncTrigger.WEBHOOK
                    )
                    run_integration_sync.delay(str(job.id))

            webhooks.mark_processed(event)
            owning_user_id = None
            if event.integration_id:
                linked_integration = integrations.get(event.integration_id)
                owning_user_id = linked_integration.user_id if linked_integration else None
            audit.record(
                action="webhook.processed",
                user_id=owning_user_id,
                integration_id=event.integration_id,
                details={"event_id": str(event.id), "event_type": event.event_type},
            )
        except Exception as exc:  # noqa: BLE001 - webhook processing must never crash silently
            if self.request.retries < MAX_RETRIES:
                backoff = BASE_BACKOFF_SECONDS * (2 ** self.request.retries)
                logger.warning(f"Webhook event {event_id} processing failed, retrying in {backoff}s: {exc}")
                raise self.retry(exc=exc, countdown=backoff)
            webhooks.mark_failed(event, str(exc))
            logger.error(f"Webhook event {event_id} failed permanently: {exc}")
    finally:
        db.close()
