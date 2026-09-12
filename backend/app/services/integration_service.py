import uuid

from sqlalchemy.orm import Session

from app.integrations.base import ProviderAPIError
from app.integrations.registry import get_provider
from app.models.enums import ProviderType, SyncTrigger
from app.models.integration import Integration
from app.repositories.audit_repo import AuditRepository
from app.repositories.integration_repo import IntegrationRepository
from app.repositories.sync_job_repo import SyncJobRepository
from app.services.oauth_state_service import OAuthStateService
from app.workers.tasks import run_integration_sync


class IntegrationNotFound(Exception):
    pass


class IntegrationService:
    def __init__(self, db: Session):
        self.db = db
        self.integrations = IntegrationRepository(db)
        self.sync_jobs = SyncJobRepository(db)
        self.audit = AuditRepository(db)
        self.oauth_state = OAuthStateService()

    def list_for_user(self, user_id: uuid.UUID) -> list[Integration]:
        return self.integrations.list_for_user(user_id)

    def get_owned(self, integration_id: uuid.UUID, user_id: uuid.UUID) -> Integration:
        integration = self.integrations.get_for_user(integration_id, user_id)
        if integration is None:
            raise IntegrationNotFound(str(integration_id))
        return integration

    def start_oauth(self, *, provider: ProviderType, user_id: uuid.UUID) -> tuple[str, str]:
        """Returns (authorization_url, state). The state is generated and
        persisted server-side in Redis (see OAuthStateService) against the
        initiating user's id, so the callback -- which cannot rely on the
        user's Authorization header still being present -- can recover
        *who* is completing the flow purely from the state token, and
        reject anything that isn't the exact state this call issued."""
        state = self.oauth_state.create_state(user_id=user_id, provider=provider)
        provider_impl = get_provider(provider)
        return provider_impl.build_authorization_url(state), state

    async def complete_oauth(self, *, provider: ProviderType, code: str, state: str) -> Integration:
        """Consumes the OAuth state to recover the user_id it was issued
        for. Raises OAuthStateError (propagated to the router as a 401) if
        the state is missing, expired, already used, or was issued for a
        different provider."""
        user_id = self.oauth_state.consume_state(state=state, provider=provider)

        provider_impl = get_provider(provider)
        token_result = await provider_impl.exchange_code_for_token(code)

        integration = self.integrations.upsert_connection(
            user_id=user_id,
            provider=provider,
            access_token=token_result.access_token,
            refresh_token=token_result.refresh_token,
            token_expires_at=token_result.expires_at,
            external_account_id=token_result.external_account_id,
            external_account_name=token_result.external_account_name,
        )
        self.audit.record(
            action="integration.connected",
            user_id=user_id,
            integration_id=integration.id,
            details={"provider": provider.value, "via": "oauth"},
        )
        return integration

    async def connect_with_token(
        self, *, provider: ProviderType, access_token: str, user_id: uuid.UUID
    ) -> Integration:
        """Local-development / demo connection path: accepts a personal
        access token directly instead of requiring a public OAuth callback
        URL. Documented in the README as the recommended way to try the
        project without deploying it publicly.

        Fetches the account identity from the provider immediately, for
        two reasons: it fails fast if the pasted token is invalid (rather
        than only discovering that on the first sync), and it records
        external_account_id so inbound webhooks for this account can
        actually be linked back to this integration -- the same linkage
        OAuth would have produced."""
        provider_impl = get_provider(provider)
        try:
            external_account_id, external_account_name = await provider_impl.fetch_account_identity(
                access_token
            )
        except ProviderAPIError as exc:
            raise ProviderAPIError(f"Could not verify token: {exc}", retryable=False) from exc

        integration = self.integrations.upsert_connection(
            user_id=user_id,
            provider=provider,
            access_token=access_token,
            external_account_id=external_account_id,
            external_account_name=external_account_name,
        )
        self.audit.record(
            action="integration.connected",
            user_id=user_id,
            integration_id=integration.id,
            details={"provider": provider.value, "via": "manual_token"},
        )
        return integration

    def disconnect(self, integration: Integration) -> Integration:
        integration = self.integrations.disconnect(integration)
        self.audit.record(
            action="integration.disconnected",
            user_id=integration.user_id,
            integration_id=integration.id,
            details={"provider": integration.provider.value},
        )
        return integration

    def trigger_sync(self, integration: Integration, trigger: SyncTrigger = SyncTrigger.MANUAL) -> uuid.UUID:
        if integration.access_token is None:
            raise ProviderAPIError("Integration is not connected", retryable=False)

        job = self.sync_jobs.create(integration_id=integration.id, trigger=trigger)
        self.audit.record(
            action="sync.started",
            user_id=integration.user_id,
            integration_id=integration.id,
            details={"sync_job_id": str(job.id), "trigger": trigger.value},
        )
        # Hand off to Celery so the HTTP request returns immediately; the
        # actual external API calls happen in the worker process.
        run_integration_sync.delay(str(job.id))
        return job.id
