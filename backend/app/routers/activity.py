from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.repositories.audit_repo import AuditRepository
from app.schemas.activity import AuditLogRead
from app.schemas.common import Page

router = APIRouter(prefix="/activity", tags=["activity"])


@router.get("", response_model=Page[AuditLogRead])
def list_activity(
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    items, total = AuditRepository(db).list_for_user(current_user.id, limit=limit, offset=offset)
    return Page(items=items, total=total, limit=limit, offset=offset)
