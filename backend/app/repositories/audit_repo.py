import uuid

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


class AuditRepository:
    def __init__(self, db: Session):
        self.db = db

    def record(
        self,
        *,
        action: str,
        user_id: uuid.UUID | None = None,
        integration_id: uuid.UUID | None = None,
        details: dict | None = None,
    ) -> AuditLog:
        entry = AuditLog(action=action, user_id=user_id, integration_id=integration_id, details=details)
        self.db.add(entry)
        self.db.commit()
        self.db.refresh(entry)
        return entry

    def list_for_user(self, user_id: uuid.UUID, *, limit: int = 50, offset: int = 0) -> tuple[list[AuditLog], int]:
        total = self.db.scalar(
            select(func.count()).select_from(AuditLog).where(AuditLog.user_id == user_id)
        ) or 0
        stmt = (
            select(AuditLog)
            .where(AuditLog.user_id == user_id)
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(self.db.scalars(stmt)), total
