"""
Password hashing and JWT issuance/verification.

Design decisions (documented further in README):
- Passwords are hashed with bcrypt via passlib. Bcrypt is intentionally slow
  and includes a per-hash salt, which protects against rainbow-table and
  brute-force attacks even if the database leaks.
- Access tokens are short-lived (default 30 min) and carry the user id (sub)
  plus a token "type" claim so refresh tokens cannot be replayed as access
  tokens and vice versa.
- Refresh tokens are longer-lived, carry a unique `jti`, and are checked
  against a server-side allowlist in Redis (see
  app/services/refresh_token_service.py) rather than trusted purely on
  signature validity. This is what makes revocation and rotation possible:
  a refresh token that's valid JWT-wise but whose jti has been revoked or
  already consumed is rejected. See README "Security considerations" for
  the tradeoff versus an HTTP-only-cookie approach.
"""
from datetime import datetime, timedelta, timezone
from typing import Any, Literal
from uuid import uuid4

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

TokenType = Literal["access", "refresh"]


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def _create_token(
    subject: str, token_type: TokenType, expires_delta: timedelta, *, jti: str | None = None
) -> tuple[str, dict[str, Any]]:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
    }
    if jti is not None:
        payload["jti"] = jti
    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token, payload


def create_access_token(user_id: str) -> str:
    token, _ = _create_token(user_id, "access", timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    return token


def create_refresh_token(user_id: str) -> tuple[str, str]:
    """Returns (token, jti). The caller is responsible for registering the
    jti in the refresh-token allowlist (see RefreshTokenService) -- this
    function only knows how to mint JWTs, not how they're tracked."""
    jti = str(uuid4())
    token, _ = _create_token(
        user_id, "refresh", timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS), jti=jti
    )
    return token, jti


class InvalidTokenError(Exception):
    pass


def decode_token(token: str, expected_type: TokenType) -> str:
    """Returns the subject (user id) if the token is valid, else raises.
    Used for access tokens, which carry no jti to check against a store."""
    return decode_token_payload(token, expected_type)["sub"]


def decode_token_payload(token: str, expected_type: TokenType) -> dict[str, Any]:
    """Returns the full decoded payload. Used for refresh tokens, where
    the caller also needs the `jti` to check against the allowlist."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except JWTError as exc:
        raise InvalidTokenError("Token is invalid or expired") from exc

    if payload.get("type") != expected_type:
        raise InvalidTokenError(f"Expected a {expected_type} token")

    if not payload.get("sub"):
        raise InvalidTokenError("Token missing subject")

    if expected_type == "refresh" and not payload.get("jti"):
        raise InvalidTokenError("Refresh token missing jti")

    return payload
