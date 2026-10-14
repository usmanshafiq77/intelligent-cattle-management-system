import os
from functools import lru_cache
from pathlib import Path, PurePath
from typing import Protocol

from app.core.config import BACKEND_DIR, get_settings


ALLOWED_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


class MediaStorage(Protocol):
    def save(self, key: str, content: bytes) -> None: ...

    def resolve(self, key: str) -> Path: ...

    def delete(self, key: str) -> None: ...


def validate_original_filename(filename: str) -> str:
    if (
        not filename
        or len(filename) > 255
        or any(ord(character) < 32 or ord(character) == 127 for character in filename)
    ):
        raise ValueError("Invalid filename")
    if PurePath(filename).name != filename or "/" in filename or "\\" in filename:
        raise ValueError("Filename must not contain a path")
    return filename


def detect_image_content_type(content: bytes) -> str:
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if (
        len(content) >= 12
        and content.startswith(b"RIFF")
        and content[8:12] == b"WEBP"
    ):
        return "image/webp"
    raise ValueError("Only valid JPEG, PNG, and WebP images are allowed")


class LocalMediaStorage:
    """Replaceable local development storage with server-generated keys."""

    def __init__(self, root: Path) -> None:
        self._root = root.resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    def _safe_path(self, key: str) -> Path:
        if not key or Path(key).is_absolute() or ".." in Path(key).parts:
            raise ValueError("Unsafe storage key")
        target = (self._root / key).resolve()
        if not target.is_relative_to(self._root):
            raise ValueError("Unsafe storage key")
        return target

    def save(self, key: str, content: bytes) -> None:
        target = self._safe_path(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(f".{target.name}.{os.getpid()}.tmp")
        try:
            with temporary.open("xb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)

    def resolve(self, key: str) -> Path:
        target = self._safe_path(key)
        if not target.is_file():
            raise FileNotFoundError(key)
        return target

    def delete(self, key: str) -> None:
        self._safe_path(key).unlink(missing_ok=True)


@lru_cache(maxsize=1)
def get_media_storage() -> MediaStorage:
    root = get_settings().MEDIA_ROOT
    if not root.is_absolute():
        root = BACKEND_DIR / root
    return LocalMediaStorage(root)
