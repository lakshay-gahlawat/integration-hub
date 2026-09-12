"""
Turns refresh tokens from "valid forever if the signature checks out" into
"valid only while the server still recognizes this specific token" --
without that, a leaked refresh token stays usable for its entire (multi-day)
lifetime with no way to cut it off.

This is a deliberately lightweight allowlist, not a full session table:
each issued refresh token's `jti` is stored in Redis with a TTL matching
the token's own expiry. A refresh token is only accepted if its jti is
still present. Using it (successfully) deletes it and issues a new one
(rotation) -- so a stolen-and-replayed refresh token gets one use before
the legitimate holder's next refresh silently fails, which is a workable
signal that something is wrong even without a full "revoke the whole
token family" implementation (see README known limitations).
"""
from app.core.config import settings
from app.core.redis_client import get_redis

_REFRESH_KEY_PREFIX = "refresh_token:"


class RefreshTokenService:
    def __init__(self):
        self.redis = get_redis()

    def register(self, *, jti: str, user_id: str) -> None:
        ttl_seconds = settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600
        self.redis.set(f"{_REFRESH_KEY_PREFIX}{jti}", user_id, ex=ttl_seconds)

    def is_active(self, jti: str) -> bool:
        return self.redis.exists(f"{_REFRESH_KEY_PREFIX}{jti}") == 1

    def revoke(self, jti: str) -> None:
        """Idempotent -- revoking an already-revoked or unknown jti is a
        no-op, so logout can always call this without first checking."""
        self.redis.delete(f"{_REFRESH_KEY_PREFIX}{jti}")
