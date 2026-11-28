"""Where uploaded files are kept. Only local disk for now; S3 can be added as another class."""

from pathlib import Path

from app.config import settings


class LocalStorage:
    """Saves files under MEDIA_ROOT on the server's disk."""

    def __init__(self, root: str) -> None:
        self.root = Path(root).resolve()

    def local_path(self, path: str) -> Path:
        """Absolute path of a stored file. Refuses paths that point outside the root."""
        target = (self.root / path).resolve()
        if not target.is_relative_to(self.root):
            raise ValueError(f"Path is outside the media root: {path}")
        return target

    def save(self, path: str, data: bytes) -> None:
        target = self.local_path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)

    def delete(self, path: str) -> None:
        self.local_path(path).unlink(missing_ok=True)


def get_storage() -> LocalStorage:
    if settings.storage_backend != "local":
        raise RuntimeError(f"Unknown STORAGE_BACKEND: {settings.storage_backend}")
    return LocalStorage(settings.media_root)
