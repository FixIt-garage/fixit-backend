"""Who can download an uploaded file (review on PR #45).

Avatars are public static files. Chat photos go through GET /uploads/{id}/file and are
visible only to their owner and to the participants of a conversation where the owner sent
them.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from tests.test_chats import accepted_chat
from tests.test_uploads import image_bytes, upload


@pytest.fixture(autouse=True)
def media_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(settings, "media_root", str(tmp_path))
    return tmp_path


def send_photo(client: TestClient, party, conversation_id: int, url: str) -> None:
    response = client.post(
        f"/conversations/{conversation_id}/messages",
        headers=party.headers,
        json={"photo_url": url},
    )
    assert response.status_code == 201, response.text


def test_chat_photo_is_visible_only_to_conversation_participants(
    client: TestClient, test_session_factory
) -> None:
    owner, master, outsider, _, conversation_id = accepted_chat(client, test_session_factory)
    photo = upload(client, owner.headers, "chat", image_bytes("JPEG")).json()
    send_photo(client, owner, conversation_id, photo["url"])

    for party in (owner, master):
        response = client.get(photo["url"], headers=party.headers)
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/jpeg"
        assert response.headers["cache-control"] == "no-store"
        assert response.content.startswith(b"\xff\xd8")  # JPEG signature

    assert client.get(photo["url"], headers=outsider.headers).status_code == 404
    assert client.get(photo["url"]).status_code == 401


def test_unsent_chat_photo_is_visible_only_to_its_owner(
    client: TestClient, test_session_factory
) -> None:
    owner, master, _, _, _ = accepted_chat(client, test_session_factory)
    photo = upload(client, owner.headers, "chat", image_bytes("JPEG")).json()

    assert client.get(photo["url"], headers=owner.headers).status_code == 200
    assert client.get(photo["url"], headers=master.headers).status_code == 404


def test_reposting_someone_elses_photo_url_does_not_give_access(
    client: TestClient, test_session_factory
) -> None:
    owner, master, _, _, conversation_id = accepted_chat(client, test_session_factory)
    photo = upload(client, owner.headers, "chat", image_bytes("JPEG")).json()

    # The master learned the URL and sends it himself: the message is not from the owner.
    send_photo(client, master, conversation_id, photo["url"])

    assert client.get(photo["url"], headers=master.headers).status_code == 404


def test_chat_photos_are_not_public_static_files(client: TestClient, test_session_factory) -> None:
    owner, _, _, _, _ = accepted_chat(client, test_session_factory)
    photo = upload(client, owner.headers, "chat", image_bytes("JPEG")).json()

    with test_session_factory() as db:
        from app.models.upload import Upload

        path = db.get(Upload, photo["id"]).path
    assert path.startswith("chat/")
    assert client.get(f"/media/{path}").status_code == 404


def test_unknown_upload_is_404(client: TestClient, test_session_factory) -> None:
    owner, _, _, _, _ = accepted_chat(client, test_session_factory)

    assert client.get("/uploads/999999/file", headers=owner.headers).status_code == 404


def test_api_responses_disable_content_sniffing(client: TestClient) -> None:
    assert client.get("/health").headers["x-content-type-options"] == "nosniff"
