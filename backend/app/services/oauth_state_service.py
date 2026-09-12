"""
Short-lived, single-use OAuth state tokens, backed by Redis.

Why this exists: the `state` parameter in an OAuth authorization-code flow
exists specifically to prevent CSRF -- without verifying it server-side, an
attacker can trick a victim's browser into completing an OAuth callback
with the attacker's authorization code, linking the attacker's external
account to the victim's Integration Hub account. Generating a random state
and never checking it (the state of this project before this pass) closes
none of that.

Design:
- create_state() stores {user_id, provider} in Redis under a random,
  unguessable key with a 10-minute TTL, and returns the key as the state
  value to hand to the provider.
- consume_state() does an atomic GETDEL: the state is read and deleted in
  one Redis operation, so even if a callback is somehow triggered twice
  with the same state (replay, double-click, browser prefetch), only the
  first one can succeed -- the second gets nothing back and is rejected.
- The callback route does NOT require the user's JWT. It can't: the
  browser redirect back from GitHub/Slack is not guaranteed to carry the
  original Authorization header (it's a plain GET from the provider's
  domain). The user's identity for completing the flow comes entirely
  from what was stored against the state token, which is exactly the
  guarantee the state token exists to provide.
"""
import json
import secrets
import uuid

from app.core.redis_client import get_redis
from app.models.enums import ProviderType

STATE_TTL_SECONDS = 600  # 10 minutes
_STATE_KEY_PREFIX = "oauth_state:"


class OAuthStateError(Exception):
    """Raised for any invalid, missing, expired, reused, or
    provider-mismatched state -- callers should treat this uniformly as
    "reject the callback", without distinguishing the exact reason to the
    client (that would leak information useful for guessing valid state
    tokens)."""


class OAuthStateService:
    def __init__(self):
        self.redis = get_redis()

    def create_state(self, *, user_id: uuid.UUID, provider: ProviderType) -> str:
        state = secrets.token_urlsafe(32)
        payload = json.dumps({"user_id": str(user_id), "provider": provider.value})
        self.redis.set(f"{_STATE_KEY_PREFIX}{state}", payload, ex=STATE_TTL_SECONDS)
        return state

    def consume_state(self, *, state: str, provider: ProviderType) -> uuid.UUID:
        """Validates and atomically consumes a state token, returning the
        user_id it was issued for. Raises OAuthStateError if the state is
        missing, expired, already used, or was issued for a different
        provider than the callback claims."""
        key = f"{_STATE_KEY_PREFIX}{state}"
        raw = self.redis.getdel(key)
        if raw is None:
            raise OAuthStateError("OAuth state is missing, expired, or already used")

        try:
            data = json.loads(raw)
            stored_provider = data["provider"]
            user_id = uuid.UUID(data["user_id"])
        except (json.JSONDecodeError, KeyError, ValueError) as exc:
            raise OAuthStateError("OAuth state payload is malformed") from exc

        if stored_provider != provider.value:
            raise OAuthStateError("OAuth state was not issued for this provider")

        return user_id
