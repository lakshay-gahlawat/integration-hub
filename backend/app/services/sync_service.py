"""
Business logic for actually running a sync. Kept separate from the Celery
task definitions (app/workers/tasks.py) so it can be unit tested without
Celery's task machinery, and so the retry/backoff *policy* (task layer)
stays decoupled from the sync *mechanics* (this module).
"""
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.integrations.base import ProviderAPIError
from app.integrations.registry import get_provider
from app.models.enums import IntegrationStatus
from app.models.sync_job import SyncJob
from app.repositories.audit_repo import AuditRepository
from app.repositories.integration_repo import IntegrationRepository
from app.repositories.sync_job_repo import SyncJobRepository

logger = get_logger(__name__)


async def execute_sync_job(db: Session, job: SyncJob) -> dict:
    """Runs the provider's sync flow for the job's integration.

    Raises ProviderAPIError on failure so the Celery task can decide,
    based on `retryable`, whether to schedule a retry with backoff or fail
    the job permanently.
    """
    integrations = IntegrationRepository(db)
    sync_jobs = SyncJobRepository(db)
    audit = AuditRepository(db)

    integration = integrations.get(job.integration_id)
    if integration is None:
        raise ProviderAPIError("Integration no longer exists", retryable=False)

    if integration.access_token is None:
        raise ProviderAPIError("Integration is disconnected", retryable=False)

    integrations.set_status(integration, IntegrationStatus.SYNCING)
    sync_jobs.mark_processing(job)

    provider_impl = get_provider(integration.provider)

    try:
        access_token = integrations.decrypt_access_token(integration)
        summary = await provider_impl.run_sync(access_token)
    except ProviderAPIError as exc:
        logger.warning(f"Sync failed for integration {integration.id}: {exc}")
        if exc.status_code == 401:
            integrations.set_status(
                integration, IntegrationStatus.NEEDS_REAUTHORIZATION, error=str(exc)
            )
        else:
            integrations.set_status(integration, IntegrationStatus.FAILED, error=str(exc))
        raise

    integrations.mark_synced(integration)
    sync_jobs.mark_success(job, summary)
    audit.record(
        action="sync.completed",
        user_id=integration.user_id,
        integration_id=integration.id,
        details={"sync_job_id": str(job.id), "summary_keys": list(summary.keys())},
    )
    return summary
