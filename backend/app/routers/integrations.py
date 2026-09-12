import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies import get_current_user
from app.integrations.base import ProviderAPIError
from app.models.enums import ProviderType
from app.models.user import User
from app.repositories.sync_job_repo import SyncJobRepository
from app.repositories.webhook_repo import WebhookRepository
from app.schemas.integration import (
    IntegrationConnectRequest,
    IntegrationRead,
    OAuthStartResponse,
    SyncTriggerResponse,
)
from app.schemas.sync_job import SyncJobRead
from app.schemas.webhook import WebhookEventRead
from app.services.integration_service import IntegrationNotFound, IntegrationService
from app.services.oauth_state_service import OAuthStateError

router = APIRouter(prefix="/integrations", tags=["integrations"])


@router.get("", response_model=list[IntegrationRead])
def list_integrations(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return IntegrationService(db).list_for_user(current_user.id)


@router.post("", response_model=IntegrationRead, status_code=status.HTTP_201_CREATED)
async def connect_integration(
    payload: IntegrationConnectRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Demo/local connection path: exchanges a personal access token
    directly instead of the full OAuth redirect flow. See GET
    /integrations/{provider}/oauth/start for the real OAuth flow."""
    service = IntegrationService(db)
    try:
        return await service.connect_with_token(
            provider=payload.provider, access_token=payload.access_token, user_id=current_user.id
        )
    except ProviderAPIError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/{provider}/oauth/start", response_model=OAuthStartResponse)
def start_oauth(
    provider: ProviderType,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    url, state = IntegrationService(db).start_oauth(provider=provider, user_id=current_user.id)
    return OAuthStartResponse(authorization_url=url, state=state)


@router.get("/{provider}/oauth/callback", response_model=IntegrationRead)
async def oauth_callback(
    provider: ProviderType,
    code: str,
    state: str,
    db: Session = Depends(get_db),
):
    """Intentionally has NO auth dependency. This route is hit by the
    browser redirecting back from GitHub/Slack, not by an authenticated
    fetch from our own frontend -- there is no guarantee an Authorization
    header survives that redirect. The user's identity instead comes from
    the `state` token, which was bound to a user_id server-side (in
    Redis) when the flow started. See OAuthStateService for why this is
    the CSRF-safe way to do this, not a workaround for one."""
    service = IntegrationService(db)
    try:
        return await service.complete_oauth(provider=provider, code=code, state=state)
    except OAuthStateError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    except ProviderAPIError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


@router.get("/{integration_id}", response_model=IntegrationRead)
def get_integration(
    integration_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return IntegrationService(db).get_owned(integration_id, current_user.id)
    except IntegrationNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found") from exc


@router.delete("/{integration_id}", status_code=status.HTTP_204_NO_CONTENT)
def disconnect_integration(
    integration_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = IntegrationService(db)
    try:
        integration = service.get_owned(integration_id, current_user.id)
    except IntegrationNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found") from exc
    service.disconnect(integration)


@router.post("/{integration_id}/sync", response_model=SyncTriggerResponse, status_code=status.HTTP_202_ACCEPTED)
def trigger_sync(
    integration_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = IntegrationService(db)
    try:
        integration = service.get_owned(integration_id, current_user.id)
    except IntegrationNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found") from exc

    try:
        job_id = service.trigger_sync(integration)
    except ProviderAPIError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return SyncTriggerResponse(sync_job_id=job_id, status="pending")


@router.get("/{integration_id}/webhooks", response_model=list[WebhookEventRead])
def integration_webhooks(
    integration_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = IntegrationService(db)
    try:
        integration = service.get_owned(integration_id, current_user.id)
    except IntegrationNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found") from exc
    return WebhookRepository(db).list_for_integration(integration.id)


@router.get("/{integration_id}/sync-jobs", response_model=list[SyncJobRead])
def integration_sync_jobs(
    integration_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = IntegrationService(db)
    try:
        integration = service.get_owned(integration_id, current_user.id)
    except IntegrationNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found") from exc
    return SyncJobRepository(db).list_for_integration(integration.id)
