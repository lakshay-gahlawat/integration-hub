"""
Encrypts OAuth access/refresh tokens before they touch the database, and
decrypts them only at the point they're needed to call an external
provider. Kept isolated here so the rest of the codebase never has to
think about key management -- it just calls encrypt_credential /
decrypt_credential.

Uses Fernet (from the `cryptography` library): AES-128-CBC for
confidentiality plus HMAC-SHA256 for integrity, in one authenticated
scheme. This is the standard, well-reviewed choice for "encrypt small
secrets at rest with a symmetric key" -- there's no reason to hand-roll
AES-GCM here when Fernet already gives authenticated encryption with a
much smaller footprint for misuse.

The key comes from INTEGRATION_ENCRYPTION_KEY (a Fernet key: 32
url-safe-base64-encoded bytes). Generate one with:

    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

Losing this key means every stored integration token becomes permanently
undecryptable -- treat it like any other production secret (rotate
deliberately, never commit it, back it up securely).
"""
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


class CredentialEncryptionError(Exception):
    """Raised when encryption/decryption cannot proceed -- missing key,
    corrupted ciphertext, or a key that doesn't match what encrypted it."""


@lru_cache
def _get_fernet() -> Fernet:
    key = settings.INTEGRATION_ENCRYPTION_KEY
    if not key:
        raise CredentialEncryptionError(
            "INTEGRATION_ENCRYPTION_KEY is not configured. Generate one with "
            "`python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"` "
            "and set it in .env."
        )
    try:
        return Fernet(key.encode())
    except ValueError as exc:
        raise CredentialEncryptionError(
            "INTEGRATION_ENCRYPTION_KEY is not a valid Fernet key"
        ) from exc


def encrypt_credential(plaintext: str) -> str:
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt_credential(ciphertext: str) -> str:
    try:
        return _get_fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken as exc:
        raise CredentialEncryptionError(
            "Could not decrypt stored credential -- wrong key or corrupted data"
        ) from exc
