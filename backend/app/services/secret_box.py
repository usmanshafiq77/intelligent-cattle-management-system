import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.services.backup_crypto import BackupCryptoError


def seal(value: str, key: bytes, *, context: bytes) -> bytes:
    nonce = os.urandom(12)
    return nonce + AESGCM(key).encrypt(nonce, value.encode("utf-8"), context)


def open_sealed(value: bytes, key: bytes, *, context: bytes) -> str:
    if len(value) < 29: raise BackupCryptoError("Encrypted credential is invalid")
    try: return AESGCM(key).decrypt(value[:12], value[12:], context).decode("utf-8")
    except Exception: raise BackupCryptoError("Encrypted credential could not be opened") from None
