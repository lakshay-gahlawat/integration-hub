import enum

from sqlalchemy import Enum as SAEnum


def sa_enum(enum_cls: type[enum.Enum]) -> SAEnum:
    """Persist enum *values* (github) rather than member names (GITHUB).

    Alembic created native Postgres ENUMs from the lowercase values; SQLAlchemy
    otherwise binds the Python member name and Postgres rejects it.
    """
    return SAEnum(
        enum_cls,
        name=enum_cls.__name__.lower(),
        values_callable=lambda members: [member.value for member in members],
        native_enum=True,
    )


class ProviderType(str, enum.Enum):
    GITHUB = "github"
    SLACK = "slack"


class IntegrationStatus(str, enum.Enum):
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    SYNCING = "syncing"
    FAILED = "failed"
    NEEDS_REAUTHORIZATION = "needs_reauthorization"


class WebhookStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"
    DUPLICATE = "duplicate"


class SyncJobStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"
    RETRYING = "retrying"


class SyncTrigger(str, enum.Enum):
    MANUAL = "manual"
    WEBHOOK = "webhook"
    SCHEDULED = "scheduled"
