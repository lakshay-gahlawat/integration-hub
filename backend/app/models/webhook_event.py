import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import ProviderType, WebhookStatus, sa_enum


class WebhookEvent(Base):
    __tablename__ = "webhook_events"
    __table_args__ = (
        # This is the core idempotency guarantee at the database level:
        # even if two requests for the same provider event race past the
        # application-level duplicate check, the unique constraint stops a
        # second row being persisted.
        UniqueConstraint("provider", "external_event_id", name="uq_webhook_provider_event"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    integration_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("integrations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    provider: Mapped[ProviderType] = mapped_column(sa_enum(ProviderType), nullable=False)

    # The provider's own event/delivery id. Used together with `provider`
    # as the idempotency key (see uq_webhook_provider_event above).
    external_event_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(255), nullable=False)

    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[WebhookStatus] = mapped_column(
        sa_enum(WebhookStatus), nullable=False, default=WebhookStatus.PENDING
    )
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    integration = relationship("Integration", back_populates="webhook_events")
