import uuid
from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.enums import ProviderType, WebhookStatus
from app.models.integration import Integration
from app.models.webhook_event import WebhookEvent


class DuplicateWebhookEvent(Exception):
    """Raised when a (provider, external_event_id) pair already exists."""


class WebhookRepository:
    def __init__(self, db: Session):
        self.db = db

    def exists(self, provider: ProviderType, external_event_id: str) -> bool:
        stmt = select(WebhookEvent.id).where(
            WebhookEvent.provider == provider,
            WebhookEvent.external_event_id == external_event_id,
        )
        return self.db.scalar(stmt) is not None

    def create(
        self,
        *,
        provider: ProviderType,
        external_event_id: str,
        event_type: str,
        payload: dict,
        integration_id: uuid.UUID | None,
    ) -> WebhookEvent:
        """Persist a new webhook event.

        Idempotency strategy: the (provider, external_event_id) pair has a
        unique DB constraint (see WebhookEvent.__table_args__). We do a
        pre-check for a friendly duplicate response, but the constraint is
        the real guarantee under concurrent delivery, since two identical
        webhooks can arrive at almost the same instant and both pass the
        pre-check before either commits.
        """
        event = WebhookEvent(
            provider=provider,
            external_event_id=external_event_id,
            event_type=event_type,
            payload=payload,
            integration_id=integration_id,
            status=WebhookStatus.PENDING,
        )
        self.db.add(event)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise DuplicateWebhookEvent(external_event_id) from exc
        self.db.refresh(event)
        return event

    def get(self, event_id: uuid.UUID) -> WebhookEvent | None:
        return self.db.get(WebhookEvent, event_id)

    def list_for_user(
        self, user_id: uuid.UUID, *, limit: int = 20, offset: int = 0
    ) -> tuple[list[WebhookEvent], int]:
        """Only returns events whose integration is owned by `user_id`.
        Events with no linked integration (e.g. a webhook that arrived
        before any matching integration existed) are not visible to any
        user through this method -- they don't belong to anyone yet."""
        total = (
            self.db.scalar(
                select(func.count())
                .select_from(WebhookEvent)
                .join(Integration, WebhookEvent.integration_id == Integration.id)
                .where(Integration.user_id == user_id)
            )
            or 0
        )
        stmt = (
            select(WebhookEvent)
            .join(Integration, WebhookEvent.integration_id == Integration.id)
            .where(Integration.user_id == user_id)
            .order_by(WebhookEvent.received_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(self.db.scalars(stmt)), total

    def get_for_user(self, event_id: uuid.UUID, user_id: uuid.UUID) -> WebhookEvent | None:
        stmt = (
            select(WebhookEvent)
            .join(Integration, WebhookEvent.integration_id == Integration.id)
            .where(WebhookEvent.id == event_id, Integration.user_id == user_id)
        )
        return self.db.scalar(stmt)

    def list_for_integration(self, integration_id: uuid.UUID, limit: int = 20) -> list[WebhookEvent]:
        stmt = (
            select(WebhookEvent)
            .where(WebhookEvent.integration_id == integration_id)
            .order_by(WebhookEvent.received_at.desc())
            .limit(limit)
        )
        return list(self.db.scalars(stmt))

    def mark_processing(self, event: WebhookEvent) -> WebhookEvent:
        event.status = WebhookStatus.PROCESSING
        event.attempt_count += 1
        self.db.commit()
        self.db.refresh(event)
        return event

    def mark_processed(self, event: WebhookEvent) -> WebhookEvent:
        event.status = WebhookStatus.PROCESSED
        event.processed_at = datetime.now(timezone.utc)
        event.last_error = None
        self.db.commit()
        self.db.refresh(event)
        return event

    def mark_failed(self, event: WebhookEvent, error: str) -> WebhookEvent:
        event.status = WebhookStatus.FAILED
        event.last_error = error[:2000]
        self.db.commit()
        self.db.refresh(event)
        return event
