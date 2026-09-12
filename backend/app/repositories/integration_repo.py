import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.crypto import decrypt_credential, encrypt_credential
from app.models.enums import IntegrationStatus, ProviderType
from app.models.integration import Integration


class IntegrationRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_for_user(self, user_id: uuid.UUID) -> list[Integration]:
        stmt = select(Integration).where(Integration.user_id == user_id).order_by(Integration.created_at.desc())
        return list(self.db.scalars(stmt))

    def get(self, integration_id: uuid.UUID) -> Integration | None:
        return self.db.get(Integration, integration_id)

    def get_for_user(self, integration_id: uuid.UUID, user_id: uuid.UUID) -> Integration | None:
        stmt = select(Integration).where(
            Integration.id == integration_id, Integration.user_id == user_id
        )
        return self.db.scalar(stmt)

    def get_by_provider(self, user_id: uuid.UUID, provider: ProviderType) -> Integration | None:
        stmt = select(Integration).where(
            Integration.user_id == user_id, Integration.provider == provider
        )
        return self.db.scalar(stmt)

    def find_by_external_account(
        self, provider: ProviderType, external_account_id: str
    ) -> Integration | None:
        stmt = select(Integration).where(
            Integration.provider == provider,
            Integration.external_account_id == external_account_id,
        )
        return self.db.scalar(stmt)

    def upsert_connection(
        self,
        *,
        user_id: uuid.UUID,
        provider: ProviderType,
        access_token: str,
        external_account_id: str | None = None,
        external_account_name: str | None = None,
        refresh_token: str | None = None,
        token_expires_at: datetime | None = None,
    ) -> Integration:
        """Stores credentials encrypted at rest (see app/core/crypto.py).
        Callers always pass plaintext tokens in; this is the one place
        that encrypts before the value touches the database."""
        integration = self.get_by_provider(user_id, provider)
        if integration is None:
            integration = Integration(user_id=user_id, provider=provider)
            self.db.add(integration)

        integration.access_token = encrypt_credential(access_token)
        integration.refresh_token = encrypt_credential(refresh_token) if refresh_token else None
        integration.token_expires_at = token_expires_at
        integration.external_account_id = external_account_id
        integration.external_account_name = external_account_name
        integration.status = IntegrationStatus.CONNECTED
        integration.last_error = None

        self.db.commit()
        self.db.refresh(integration)
        return integration

    @staticmethod
    def decrypt_access_token(integration: Integration) -> str:
        """The only place the plaintext access token should ever be
        reconstructed -- callers use this immediately before making an
        external API call, and never persist or log the result."""
        if integration.access_token is None:
            raise ValueError("Integration has no stored access token")
        return decrypt_credential(integration.access_token)

    def disconnect(self, integration: Integration) -> Integration:
        integration.status = IntegrationStatus.DISCONNECTED
        integration.access_token = None
        integration.refresh_token = None
        self.db.commit()
        self.db.refresh(integration)
        return integration

    def set_status(self, integration: Integration, status: IntegrationStatus, error: str | None = None) -> Integration:
        integration.status = status
        integration.last_error = error
        self.db.commit()
        self.db.refresh(integration)
        return integration

    def mark_synced(self, integration: Integration) -> Integration:
        integration.last_synced_at = datetime.now(timezone.utc)
        integration.status = IntegrationStatus.CONNECTED
        integration.last_error = None
        self.db.commit()
        self.db.refresh(integration)
        return integration
