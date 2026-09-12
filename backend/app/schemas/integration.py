import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import IntegrationStatus, ProviderType


class IntegrationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    provider: ProviderType
    status: IntegrationStatus
    external_account_id: str | None
    external_account_name: str | None
    last_synced_at: datetime | None
    last_error: str | None
    created_at: datetime
    updated_at: datetime


class IntegrationConnectRequest(BaseModel):
    """Used for the manual/demo connection flow where a developer pastes a
    personal access token instead of completing the full OAuth redirect
    dance (useful for local testing without a public callback URL)."""

    provider: ProviderType
    access_token: str


class OAuthStartResponse(BaseModel):
    authorization_url: str
    state: str


class SyncTriggerResponse(BaseModel):
    sync_job_id: uuid.UUID
    status: str
