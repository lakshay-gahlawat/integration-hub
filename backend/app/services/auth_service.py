from sqlalchemy.orm import Session

from app.core.security import (
    InvalidTokenError,
    create_access_token,
    create_refresh_token,
    decode_token_payload,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.repositories.user_repo import UserRepository
from app.schemas.auth import TokenPair
from app.services.refresh_token_service import RefreshTokenService


class EmailAlreadyRegistered(Exception):
    pass


class InvalidCredentials(Exception):
    pass


class AuthService:
    def __init__(self, db: Session):
        self.db = db
        self.users = UserRepository(db)
        self.refresh_tokens = RefreshTokenService()

    def register(self, *, email: str, password: str, full_name: str) -> User:
        if self.users.get_by_email(email):
            raise EmailAlreadyRegistered(email)
        return self.users.create(
            email=email, hashed_password=hash_password(password), full_name=full_name
        )

    def authenticate(self, *, email: str, password: str) -> User:
        user = self.users.get_by_email(email)
        if user is None or not verify_password(password, user.hashed_password):
            raise InvalidCredentials()
        return user

    def issue_tokens(self, user: User) -> TokenPair:
        refresh_token, jti = create_refresh_token(str(user.id))
        self.refresh_tokens.register(jti=jti, user_id=str(user.id))
        return TokenPair(
            access_token=create_access_token(str(user.id)),
            refresh_token=refresh_token,
        )

    def rotate_refresh_token(self, refresh_token: str) -> TokenPair:
        """Validates a refresh token's signature/type AND checks it's
        still in the active allowlist, then consumes it and issues a
        brand-new access/refresh pair. Raises InvalidTokenError for any
        failure -- expired, malformed, wrong type, or a jti that's been
        revoked or already rotated away. Callers shouldn't need to
        distinguish those cases; they're all "reject and require login
        again" from the client's perspective."""
        payload = decode_token_payload(refresh_token, expected_type="refresh")
        user_id = payload["sub"]
        jti = payload["jti"]

        if not self.refresh_tokens.is_active(jti):
            raise InvalidTokenError("Refresh token has been revoked or already used")

        # Rotation: the old token can never be used again, successfully or
        # not, the moment a new one is issued from it.
        self.refresh_tokens.revoke(jti)

        new_refresh_token, new_jti = create_refresh_token(user_id)
        self.refresh_tokens.register(jti=new_jti, user_id=user_id)
        return TokenPair(
            access_token=create_access_token(user_id),
            refresh_token=new_refresh_token,
        )

    def revoke_refresh_token(self, refresh_token: str) -> None:
        """Used for logout. Best-effort and silent about *why* nothing
        happened -- an already-expired or malformed token during logout
        isn't an error worth surfacing, the end state (not usable) is the
        same either way."""
        try:
            payload = decode_token_payload(refresh_token, expected_type="refresh")
        except InvalidTokenError:
            return
        self.refresh_tokens.revoke(payload["jti"])
