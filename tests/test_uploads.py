import io
from pathlib import Path

import pillow_heif
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.config import settings
from app.models.upload import Upload, UploadKind

pillow_heif.register_heif_opener()


@pytest.fixture(autouse=True)
def media_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Store files in a temporary folder, so tests do not touch the real media folder."""
    monkeypatch.setattr(settings, "media_root", str(tmp_path))
    return tmp_path


def auth_headers(client: TestClient, email: str = "uploader@example.com") -> dict[str, str]:
    response = client.post(
        "/auth/register",
        json={
            "email": email,
            "password": "TestPassword123!",
            "first_name": "Test",
            "last_name": "User",
        },
    )
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def image_bytes(image_format: str, size: tuple[int, int] = (800, 600), **save_args) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, "orange").save(buffer, format=image_format, **save_args)
    return buffer.getvalue()


def upload(client: TestClient, headers: dict, kind: str, data: bytes, name: str = "photo.jpg"):
    return client.post(
        "/uploads",
        data={"kind": kind},
        files={"file": (name, data, "image/jpeg")},
        headers=headers,
    )


def test_upload_chat_photo(client: TestClient, test_session_factory, media_root: Path) -> None:
    response = upload(client, auth_headers(client), "chat", image_bytes("PNG"), "photo.png")

    assert response.status_code == 201
    body = response.json()
    assert body["kind"] == "chat"
    assert body["content_type"] == "image/jpeg"
    assert "/media/chat/" in body["url"]

    with test_session_factory() as db:
        stored = db.get(Upload, body["id"])
        assert stored is not None
        assert stored.kind == UploadKind.CHAT
        assert (media_root / stored.path).is_file()
        assert (media_root / stored.path).stat().st_size == body["size_bytes"]


def test_avatar_is_resized_and_set_on_profile(client: TestClient, media_root: Path) -> None:
    headers = auth_headers(client)

    response = upload(client, headers, "avatar", image_bytes("JPEG", (1200, 800)))

    assert response.status_code == 201
    url = response.json()["url"]
    assert "/media/avatars/" in url
    stored = media_root / url.split("/media/", 1)[1]
    with Image.open(stored) as image:
        assert image.size == (settings.avatar_size_px, settings.avatar_size_px)

    profile = client.get("/users/me", headers=headers)
    assert profile.json()["avatar_url"] == url


def test_heic_is_accepted_and_converted_to_jpeg(client: TestClient) -> None:
    response = upload(client, auth_headers(client), "chat", image_bytes("HEIF"), "photo.heic")

    assert response.status_code == 201
    assert response.json()["content_type"] == "image/jpeg"


def test_location_metadata_is_removed(client: TestClient, media_root: Path) -> None:
    exif = Image.Exif()
    exif[0x010F] = "PhoneMaker"  # camera make, stands in for GPS and other metadata
    data = image_bytes("JPEG", exif=exif.tobytes())

    response = upload(client, auth_headers(client), "chat", data)

    assert response.status_code == 201
    stored = media_root / response.json()["url"].split("/media/", 1)[1]
    with Image.open(stored) as image:
        assert len(image.getexif()) == 0


@pytest.mark.parametrize(
    ("data", "name"),
    [
        (b"this is not an image", "photo.jpg"),
        (image_bytes("GIF"), "animation.gif"),
    ],
    ids=["text", "gif"],
)
def test_wrong_type_is_rejected(
    client: TestClient, test_session_factory, data: bytes, name: str
) -> None:
    response = upload(client, auth_headers(client), "chat", data, name)

    assert response.status_code == 415
    assert response.json()["code"] == "unsupported_media_type"
    with test_session_factory() as db:
        assert db.query(Upload).count() == 0


def test_too_large_file_is_rejected(
    client: TestClient, test_session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "max_upload_size_mb", 1)

    response = upload(client, auth_headers(client), "chat", b"x" * (1024 * 1024 + 1))

    assert response.status_code == 413
    assert response.json()["code"] == "payload_too_large"
    with test_session_factory() as db:
        assert db.query(Upload).count() == 0


def test_unknown_kind_is_rejected(client: TestClient) -> None:
    response = upload(client, auth_headers(client), "document", image_bytes("PNG"))

    assert response.status_code == 422
    fields = [detail["field"] for detail in response.json()["details"]]
    assert "body.kind" in fields


def test_upload_without_token_is_rejected(client: TestClient) -> None:
    response = upload(client, {}, "chat", image_bytes("PNG"))

    assert response.status_code == 401