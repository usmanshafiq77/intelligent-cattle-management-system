"""Authenticated streaming encryption for ICMS backup artifacts."""
import base64
import hashlib
import json
import os
import struct
from pathlib import Path

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

MAGIC = b"ICMSBAK1"
MAX_HEADER = 16_384


class BackupCryptoError(ValueError): pass


def decode_key(encoded: str) -> bytes:
    try: key = base64.urlsafe_b64decode(encoded.encode("ascii"))
    except Exception: raise BackupCryptoError("Backup key is not valid URL-safe base64") from None
    if len(key) != 32: raise BackupCryptoError("Backup key must decode to exactly 32 bytes")
    return key


def encrypt_file(source: Path, destination: Path, *, key: bytes, key_id: str) -> dict:
    if source.resolve() == destination.resolve(): raise BackupCryptoError("Source and destination must differ")
    nonce = os.urandom(12)
    header = json.dumps({"algorithm": "AES-256-GCM", "key_id": key_id, "nonce": base64.urlsafe_b64encode(nonce).decode("ascii")}, separators=(",", ":"), sort_keys=True).encode()
    if len(header) > MAX_HEADER: raise BackupCryptoError("Backup header is too large")
    prefix = MAGIC + struct.pack(">I", len(header)) + header
    encryptor = Cipher(algorithms.AES(key), modes.GCM(nonce)).encryptor(); encryptor.authenticate_additional_data(prefix)
    plain_hash, encrypted_hash = hashlib.sha256(), hashlib.sha256()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with source.open("rb") as src, destination.open("xb") as dst:
        os.chmod(destination, 0o600); dst.write(prefix); encrypted_hash.update(prefix)
        while chunk := src.read(1024 * 1024): plain_hash.update(chunk); out = encryptor.update(chunk); dst.write(out); encrypted_hash.update(out)
        final = encryptor.finalize(); dst.write(final); encrypted_hash.update(final); dst.write(encryptor.tag); encrypted_hash.update(encryptor.tag)
    return {"plaintext_sha256": plain_hash.hexdigest(), "encrypted_sha256": encrypted_hash.hexdigest(), "size_bytes": destination.stat().st_size, "key_id": key_id}


def inspect_header(source: Path) -> dict:
    with source.open("rb") as stream:
        magic = stream.read(len(MAGIC)); raw_length = stream.read(4)
        if magic != MAGIC or len(raw_length) != 4: raise BackupCryptoError("Not an ICMS encrypted backup")
        length = struct.unpack(">I", raw_length)[0]
        if length <= 0 or length > MAX_HEADER: raise BackupCryptoError("Invalid backup header")
        try: header = json.loads(stream.read(length))
        except Exception: raise BackupCryptoError("Invalid backup header") from None
    if header.get("algorithm") != "AES-256-GCM" or not header.get("key_id"): raise BackupCryptoError("Unsupported backup encryption metadata")
    return header


def decrypt_file(source: Path, destination: Path, *, keys: dict[str, bytes]) -> dict:
    total = source.stat().st_size
    with source.open("rb") as src:
        prefix_start = src.read(len(MAGIC) + 4)
        if prefix_start[:len(MAGIC)] != MAGIC: raise BackupCryptoError("Not an ICMS encrypted backup")
        length = struct.unpack(">I", prefix_start[-4:])[0]
        if length <= 0 or length > MAX_HEADER: raise BackupCryptoError("Invalid backup header")
        header_bytes = src.read(length); prefix = prefix_start + header_bytes
        try: header = json.loads(header_bytes)
        except Exception: raise BackupCryptoError("Invalid backup header") from None
        key = keys.get(header.get("key_id"))
        if key is None: raise BackupCryptoError("Required recovery key is unavailable")
        nonce = base64.urlsafe_b64decode(header["nonce"]); cipher_length = total - len(prefix) - 16
        if cipher_length < 0: raise BackupCryptoError("Encrypted backup is truncated")
        src.seek(total - 16); tag = src.read(16); src.seek(len(prefix))
        decryptor = Cipher(algorithms.AES(key), modes.GCM(nonce, tag)).decryptor(); decryptor.authenticate_additional_data(prefix)
        digest = hashlib.sha256(); remaining = cipher_length
        try:
            with destination.open("xb") as dst:
                os.chmod(destination, 0o600)
                while remaining:
                    chunk = src.read(min(1024 * 1024, remaining)); remaining -= len(chunk); out = decryptor.update(chunk); dst.write(out); digest.update(out)
                final = decryptor.finalize(); dst.write(final); digest.update(final)
        except Exception:
            destination.unlink(missing_ok=True)
            raise BackupCryptoError("Backup authentication or decryption failed") from None
    return {"plaintext_sha256": digest.hexdigest(), "key_id": header["key_id"]}
