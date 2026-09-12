"""enforce not null on server-defaulted timestamp columns

Revision ID: 0002_timestamp_not_null
Revises: 0001_initial
Create Date: 2026-08-27

The ORM models declare these columns as non-optional (Mapped[datetime]),
which SQLAlchemy 2.0 style maps to NOT NULL -- but the original migration
didn't set nullable=False explicitly, leaving a drift between what the
models promise and what the database actually enforces. In practice every
row always gets a value via server_default=now(), so this is a
correctness/integrity fix rather than a behavior change.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_timestamp_not_null"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_COLUMNS = [
    ("users", "created_at"),
    ("users", "updated_at"),
    ("integrations", "created_at"),
    ("integrations", "updated_at"),
    ("sync_jobs", "created_at"),
    ("webhook_events", "received_at"),
    ("audit_logs", "created_at"),
]


def upgrade() -> None:
    for table, column in _COLUMNS:
        op.alter_column(table, column, existing_type=sa.DateTime(timezone=True), nullable=False)


def downgrade() -> None:
    for table, column in _COLUMNS:
        op.alter_column(table, column, existing_type=sa.DateTime(timezone=True), nullable=True)
