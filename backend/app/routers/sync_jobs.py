import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.repositories.sync_job_repo import SyncJobRepository
from app.schemas.common import Page
from app.schemas.sync_job import SyncJobRead

router = APIRouter(prefix="/sync-jobs", tags=["sync-jobs"])


@router.get("", response_model=Page[SyncJobRead])
def list_sync_jobs(
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    items, total = SyncJobRepository(db).list_for_user(current_user.id, limit=limit, offset=offset)
    return Page(items=items, total=total, limit=limit, offset=offset)


@router.get("/{job_id}", response_model=SyncJobRead)
def get_sync_job(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job = SyncJobRepository(db).get_for_user(job_id, current_user.id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sync job not found")
    return job
