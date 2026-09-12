from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import InvalidTokenError
from app.db.session import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.auth import AuthResponse, LoginRequest, RefreshRequest, TokenPair
from app.schemas.user import UserCreate, UserRead
from app.services.auth_service import AuthService, EmailAlreadyRegistered, InvalidCredentials

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, db: Session = Depends(get_db)):
    service = AuthService(db)
    try:
        user = service.register(email=payload.email, password=payload.password, full_name=payload.full_name)
    except EmailAlreadyRegistered as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered") from exc

    tokens = service.issue_tokens(user)
    return AuthResponse(**tokens.model_dump(), user=UserRead.model_validate(user))


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    service = AuthService(db)
    try:
        user = service.authenticate(email=payload.email, password=payload.password)
    except InvalidCredentials as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password"
        ) from exc

    tokens = service.issue_tokens(user)
    return AuthResponse(**tokens.model_dump(), user=UserRead.model_validate(user))


@router.post("/refresh", response_model=TokenPair)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
    """Rotates the refresh token on every use: the token presented here is
    immediately invalidated and a new access/refresh pair is issued in its
    place. Presenting the same refresh token twice always fails the second
    time -- by design, not as a bug -- since rotation is what makes a
    stolen-and-replayed refresh token detectable (see AuthService.rotate_refresh_token)."""
    service = AuthService(db)
    try:
        return service.rotate_refresh_token(payload.refresh_token)
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid, expired, or already-used refresh token"
        ) from exc


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(payload: RefreshRequest, db: Session = Depends(get_db)):
    """Revokes the given refresh token so it can no longer be used to
    obtain new access tokens. Access tokens already issued remain valid
    until they naturally expire (at most ACCESS_TOKEN_EXPIRE_MINUTES) --
    documented in the README as an accepted tradeoff of the bearer-token
    approach rather than an oversight."""
    AuthService(db).revoke_refresh_token(payload.refresh_token)


@router.get("/me", response_model=UserRead)
def me(current_user: User = Depends(get_current_user)):
    return UserRead.model_validate(current_user)
