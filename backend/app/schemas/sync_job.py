import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.models.enums import SyncJobStatus, SyncTrigger


class SyncJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    integration_id: uuid.UUID
    trigger: SyncTrigger
    status: SyncJobStatus
    attempt_count: int
    result_summary: dict[str, Any] | None
    error_message: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
