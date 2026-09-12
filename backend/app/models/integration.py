import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import IntegrationStatus, ProviderType, sa_enum


class Integration(Base):
    __tablename__ = "integrations"
    __table_args__ = (
        # A user can only have one active connection per provider. This keeps
        # the "add integration" UX simple; supporting multiple accounts per
        # provider is a documented future improvement.
        UniqueConstraint("user_id", "provider", name="uq_integration_user_provider"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[ProviderType] = mapped_column(sa_enum(ProviderType), nullable=False)
    status: Mapped[IntegrationStatus] = mapped_column(
        sa_enum(IntegrationStatus), nullable=False, default=IntegrationStatus.DISCONNECTED
    )

    # External account identifiers, e.g. GitHub login or Slack team id.
    external_account_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    external_account_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # OAuth credentials. In this demo they are stored as plain text columns
    # scoped by DB access controls; see README "Security considerations" for
    # why a production system should encrypt these at rest (e.g. via
    # pgcrypto or an external secrets manager / KMS envelope encryption).
    access_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user = relationship("User", back_populates="integrations")
    webhook_events = relationship(
        "WebhookEvent", back_populates="integration", cascade="all, delete-orphan"
    )
    sync_jobs = relationship(
        "SyncJob", back_populates="integration", cascade="all, delete-orphan"
    )
