"""Where uploaded files are kept. Only local disk for now; S3 can be added as another class."""

from pathlib import Path

from app.config import settings


class LocalStorage:
    """Saves files under MEDIA_ROOT on the server's disk."""

    def __init__(self, root: str) -> None:
        self.root = Path(root)

    def save(self, path: str, data: bytes) -> None:
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)

    def delete(self, path: str) -> None:
        (self.root / path).unlink(missing_ok=True)


def get_storage() -> LocalStorage:
    if settings.storage_backend != "local":
        raise RuntimeError(f"Unknown STORAGE_BACKEND: {settings.storage_backend}")
    return LocalStorage(settings.media_root)