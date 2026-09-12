import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.models.enums import ProviderType, WebhookStatus


class WebhookEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    integration_id: uuid.UUID | None
    provider: ProviderType
    external_event_id: str
    event_type: str
    status: WebhookStatus
    attempt_count: int
    last_error: str | None
    received_at: datetime
    processed_at: datetime | None


class WebhookEventDetail(WebhookEventRead):
    payload: dict[str, Any]


class WebhookReceiveAck(BaseModel):
    accepted: bool
    event_id: uuid.UUID | None = None
    duplicate: bool = False
