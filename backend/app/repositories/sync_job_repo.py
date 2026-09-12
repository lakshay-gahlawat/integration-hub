import uuid
from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models.enums import SyncJobStatus, SyncTrigger
from app.models.integration import Integration
from app.models.sync_job import SyncJob


class SyncJobRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, *, integration_id: uuid.UUID, trigger: SyncTrigger) -> SyncJob:
        job = SyncJob(integration_id=integration_id, trigger=trigger, status=SyncJobStatus.PENDING)
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return job

    def get(self, job_id: uuid.UUID) -> SyncJob | None:
        return self.db.get(SyncJob, job_id)

    def list_for_integration(self, integration_id: uuid.UUID, limit: int = 20) -> list[SyncJob]:
        stmt = (
            select(SyncJob)
            .where(SyncJob.integration_id == integration_id)
            .order_by(SyncJob.created_at.desc())
            .limit(limit)
        )
        return list(self.db.scalars(stmt))

    def list_for_user(
        self, user_id: uuid.UUID, *, limit: int = 20, offset: int = 0
    ) -> tuple[list[SyncJob], int]:
        """Only returns sync jobs whose integration is owned by `user_id`."""
        total = (
            self.db.scalar(
                select(func.count())
                .select_from(SyncJob)
                .join(Integration, SyncJob.integration_id == Integration.id)
                .where(Integration.user_id == user_id)
            )
            or 0
        )
        stmt = (
            select(SyncJob)
            .join(Integration, SyncJob.integration_id == Integration.id)
            .where(Integration.user_id == user_id)
            .order_by(SyncJob.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(self.db.scalars(stmt)), total

    def get_for_user(self, job_id: uuid.UUID, user_id: uuid.UUID) -> SyncJob | None:
        stmt = (
            select(SyncJob)
            .join(Integration, SyncJob.integration_id == Integration.id)
            .where(SyncJob.id == job_id, Integration.user_id == user_id)
        )
        return self.db.scalar(stmt)

    def mark_processing(self, job: SyncJob) -> SyncJob:
        job.status = SyncJobStatus.PROCESSING
        job.attempt_count += 1
        job.started_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(job)
        return job

    def mark_retrying(self, job: SyncJob, error: str) -> SyncJob:
        job.status = SyncJobStatus.RETRYING
        job.error_message = error[:2000]
        self.db.commit()
        self.db.refresh(job)
        return job

    def mark_success(self, job: SyncJob, summary: dict) -> SyncJob:
        job.status = SyncJobStatus.SUCCESS
        job.result_summary = summary
        job.error_message = None
        job.finished_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(job)
        return job

    def mark_failed(self, job: SyncJob, error: str) -> SyncJob:
        job.status = SyncJobStatus.FAILED
        job.error_message = error[:2000]
        job.finished_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(job)
        return job
