import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies import get_current_user
from app.integrations.base import WebhookVerificationError
from app.models.enums import ProviderType
from app.models.user import User
from app.repositories.webhook_repo import WebhookRepository
from app.schemas.common import Page
from app.schemas.webhook import WebhookEventDetail, WebhookEventRead, WebhookReceiveAck
from app.services.webhook_service import WebhookService

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/{provider}", response_model=WebhookReceiveAck, status_code=status.HTTP_200_OK)
async def receive_webhook(provider: ProviderType, request: Request, db: Session = Depends(get_db)):
    """Public endpoint -- providers cannot present a JWT, so this route is
    intentionally excluded from auth. Trust instead comes from verifying
    the provider's cryptographic signature over the raw body (see
    app/integrations/{provider}_provider.py::verify_webhook)."""
    raw_body = await request.body()
    headers = {k.lower(): v for k, v in request.headers.items()}

    service = WebhookService(db)
    try:
        event, is_duplicate = service.receive(provider=provider, headers=headers, raw_body=raw_body)
    except WebhookVerificationError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    if is_duplicate:
        return WebhookReceiveAck(accepted=True, duplicate=True)

    return WebhookReceiveAck(accepted=True, event_id=event.id, duplicate=False)


@router.get("", response_model=Page[WebhookEventRead])
def list_webhooks(
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    items, total = WebhookRepository(db).list_for_user(current_user.id, limit=limit, offset=offset)
    return Page(items=items, total=total, limit=limit, offset=offset)


@router.get("/{event_id}", response_model=WebhookEventDetail)
def get_webhook(
    event_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    event = WebhookRepository(db).get_for_user(event_id, current_user.id)
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook event not found")
    return event
