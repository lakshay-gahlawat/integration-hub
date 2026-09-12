"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-08-25

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

provider_enum = postgresql.ENUM("github", "slack", name="providertype", create_type=False)
integration_status_enum = postgresql.ENUM(
    "connected", "disconnected", "syncing", "failed", "needs_reauthorization",
    name="integrationstatus", create_type=False,
)
webhook_status_enum = postgresql.ENUM(
    "pending", "processing", "processed", "failed", "duplicate",
    name="webhookstatus", create_type=False,
)
sync_job_status_enum = postgresql.ENUM(
    "pending", "processing", "success", "failed", "retrying",
    name="syncjobstatus", create_type=False,
)
sync_trigger_enum = postgresql.ENUM(
    "manual", "webhook", "scheduled", name="synctrigger", create_type=False
)


def upgrade() -> None:
    bind = op.get_bind()
    provider_enum.create(bind, checkfirst=True)
    integration_status_enum.create(bind, checkfirst=True)
    webhook_status_enum.create(bind, checkfirst=True)
    sync_job_status_enum.create(bind, checkfirst=True)
    sync_trigger_enum.create(bind, checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "integrations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("provider", provider_enum, nullable=False),
        sa.Column("status", integration_status_enum, nullable=False, server_default="disconnected"),
        sa.Column("external_account_id", sa.String(255), nullable=True),
        sa.Column("external_account_name", sa.String(255), nullable=True),
        sa.Column("access_token", sa.Text(), nullable=True),
        sa.Column("refresh_token", sa.Text(), nullable=True),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "provider", name="uq_integration_user_provider"),
    )
    op.create_index("ix_integrations_user_id", "integrations", ["user_id"])

    op.create_table(
        "webhook_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "integration_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("integrations.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column("provider", provider_enum, nullable=False),
        sa.Column("external_event_id", sa.String(255), nullable=False),
        sa.Column("event_type", sa.String(255), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("status", webhook_status_enum, nullable=False, server_default="pending"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("provider", "external_event_id", name="uq_webhook_provider_event"),
    )
    op.create_index("ix_webhook_events_integration_id", "webhook_events", ["integration_id"])
    op.create_index("ix_webhook_events_external_event_id", "webhook_events", ["external_event_id"])

    op.create_table(
        "sync_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "integration_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("integrations.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("trigger", sync_trigger_enum, nullable=False),
        sa.Column("status", sync_job_status_enum, nullable=False, server_default="pending"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("result_summary", postgresql.JSONB(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_sync_jobs_integration_id", "sync_jobs", ["integration_id"])

    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True,
        ),
        sa.Column(
            "integration_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("integrations.id", ondelete="CASCADE"), nullable=True,
        ),
        sa.Column("action", sa.String(255), nullable=False),
        sa.Column("details", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])
    op.create_index("ix_audit_logs_integration_id", "audit_logs", ["integration_id"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("sync_jobs")
    op.drop_table("webhook_events")
    op.drop_table("integrations")
    op.drop_table("users")

    bind = op.get_bind()
    sync_trigger_enum.drop(bind, checkfirst=True)
    sync_job_status_enum.drop(bind, checkfirst=True)
    webhook_status_enum.drop(bind, checkfirst=True)
    integration_status_enum.drop(bind, checkfirst=True)
    provider_enum.drop(bind, checkfirst=True)
