"""Chats (FIX-31): opened when a master accepts an issue, readable only by its two participants."""

import threading
from dataclasses import dataclass

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.security import create_access_token
from app.models.catalog import Category
from app.models.chat import Conversation, Message
from app.models.company import Company
from app.models.master import Master
from app.models.user import User, UserRole
from app.services import chat as chat_service
from app.services.chat import ISSUE_ACCEPTED_TEXT


@dataclass
class Party:
    user_id: int
    headers: dict[str, str]


def create_party(
    db,
    email: str,
    role: UserRole,
    first_name: str = "Test",
    last_name: str = "User",
) -> Party:
    user = User(
        email=email,
        password_hash="not-used-in-tests",
        first_name=first_name,
        last_name=last_name,
        role=role,
    )
    db.add(user)
    db.flush()
    token = create_access_token(str(user.id))
    return Party(user_id=user.id, headers={"Authorization": f"Bearer {token}"})


def create_master(db, email: str, last_name: str, company_id: int | None = None):
    party = create_party(db, email, UserRole.MASTER, first_name="Ivan", last_name=last_name)
    master = Master(user_id=party.user_id, company_id=company_id)
    db.add(master)
    db.flush()
    return party, master.id


def first_category_id(db) -> int:
    category_id = db.scalar(select(Category.id).order_by(Category.id))
    assert category_id is not None
    return category_id


def create_issue(client: TestClient, owner: Party, category_id: int, **assignee) -> int:
    response = client.post(
        "/issues",
        headers=owner.headers,
        json={
            "title": "Leaking tap",
            "description": "The kitchen tap is leaking",
            "category_id": category_id,
            **assignee,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def accept(client: TestClient, issue_id: int, master: Party) -> None:
    response = client.post(f"/issues/{issue_id}/accept", headers=master.headers)
    assert response.status_code == 200, response.text


def accepted_chat(client: TestClient, test_session_factory):
    """A client, a master and the conversation opened by accepting the client's issue."""
    with test_session_factory() as db:
        category_id = first_category_id(db)
        owner = create_party(db, "chat-owner@example.com", UserRole.CLIENT, "Olena", "Koval")
        master, master_id = create_master(db, "chat-master@example.com", "Petrenko")
        outsider = create_party(db, "chat-outsider@example.com", UserRole.CLIENT)
        db.commit()

    issue_id = create_issue(client, owner, category_id, assignee_master_id=master_id)
    accept(client, issue_id, master)

    conversations = client.get("/conversations", headers=owner.headers).json()["items"]
    assert len(conversations) == 1
    return owner, master, outsider, issue_id, conversations[0]["id"]


def unread(client: TestClient, party: Party) -> int:
    response = client.get("/conversations", headers=party.headers)
    assert response.status_code == 200, response.text
    return response.json()["items"][0]["unread_count"]


def test_accepting_issue_opens_conversation_with_system_message(
    client: TestClient,
    test_session_factory,
) -> None:
    owner, master, _, issue_id, conversation_id = accepted_chat(client, test_session_factory)

    owner_view = client.get("/conversations", headers=owner.headers).json()
    assert owner_view["total"] == 1
    item = owner_view["items"][0]
    assert item["issue"] == {"id": issue_id, "title": "Leaking tap", "status": "accepted"}
    assert item["other_party"]["id"] == master.user_id
    assert item["other_party"]["last_name"] == "Petrenko"
    assert item["last_message"]["is_system"] is True
    assert item["last_message"]["sender_id"] is None
    assert item["last_message"]["text"] == ISSUE_ACCEPTED_TEXT
    assert item["unread_count"] == 0

    master_view = client.get("/conversations", headers=master.headers).json()
    assert master_view["items"][0]["id"] == conversation_id
    assert master_view["items"][0]["other_party"]["id"] == owner.user_id

    with test_session_factory() as db:
        conversation = db.get(Conversation, conversation_id)
        assert conversation is not None
        assert conversation.issue_id == issue_id
        assert conversation.client_id == owner.user_id
        assert conversation.master_user_id == master.user_id


def test_participants_exchange_messages_and_see_unread_counts(
    client: TestClient,
    test_session_factory,
) -> None:
    owner, master, _, _, conversation_id = accepted_chat(client, test_session_factory)
    url = f"/conversations/{conversation_id}/messages"

    sent = client.post(url, headers=owner.headers, json={"text": "  Коли зможете прийти?  "})
    assert sent.status_code == 201, sent.text
    assert sent.json()["text"] == "Коли зможете прийти?"
    assert sent.json()["sender_id"] == owner.user_id
    assert sent.json()["read_at"] is None

    assert unread(client, master) == 1
    assert unread(client, owner) == 0

    photo = "https://cdn.example.com/chat/tap.jpg"
    reply = client.post(url, headers=master.headers, json={"text": "Завтра", "photo_url": photo})
    assert reply.status_code == 201, reply.text
    assert reply.json()["photo_url"] == photo

    assert unread(client, owner) == 1
    owner_item = client.get("/conversations", headers=owner.headers).json()["items"][0]
    assert owner_item["last_message"]["id"] == reply.json()["id"]
    assert owner_item["last_message_at"] == reply.json()["created_at"]

    read_url = f"/conversations/{conversation_id}/read"
    shown = {"last_read_message_id": reply.json()["id"]}
    marked = client.post(read_url, headers=master.headers, json=shown)
    assert marked.status_code == 200, marked.text
    assert marked.json() == {"marked_read": 1}
    assert unread(client, master) == 0
    assert unread(client, owner) == 1  # the master's reply is still unread for the client

    again = client.post(read_url, headers=master.headers, json=shown)
    assert again.json() == {"marked_read": 0}

    with test_session_factory() as db:
        owner_message = db.get(Message, sent.json()["id"])
        master_message = db.get(Message, reply.json()["id"])
        assert owner_message is not None and owner_message.read_at is not None
        assert master_message is not None and master_message.read_at is None


def test_read_marks_only_messages_the_app_has_shown(
    client: TestClient,
    test_session_factory,
) -> None:
    owner, master, _, _, conversation_id = accepted_chat(client, test_session_factory)
    url = f"/conversations/{conversation_id}/messages"
    read_url = f"/conversations/{conversation_id}/read"

    first = client.post(url, headers=owner.headers, json={"text": "Добрий день"}).json()
    shown = client.get(url, headers=master.headers).json()["items"]
    assert shown[0]["id"] == first["id"]

    # The client writes again after the master's app loaded the chat but before it sent /read.
    second = client.post(url, headers=owner.headers, json={"text": "Ви тут?"}).json()

    marked = client.post(
        read_url, headers=master.headers, json={"last_read_message_id": shown[0]["id"]}
    )
    assert marked.status_code == 200, marked.text
    assert marked.json() == {"marked_read": 1}
    assert unread(client, master) == 1

    with test_session_factory() as db:
        first_message = db.get(Message, first["id"])
        second_message = db.get(Message, second["id"])
        assert first_message is not None and first_message.read_at is not None
        assert second_message is not None and second_message.read_at is None

    for body in ({}, {"last_read_message_id": 0}, {"last_read_message_id": 1, "extra": 1}):
        response = client.post(read_url, headers=master.headers, json=body)
        assert response.status_code == 422, (body, response.text)


def test_polling_never_skips_a_message_sent_at_the_same_time(
    client: TestClient,
    test_session_factory,
) -> None:
    owner, master, _, _, conversation_id = accepted_chat(client, test_session_factory)
    url = f"/conversations/{conversation_id}/messages"
    cursor = client.get(url, headers=owner.headers).json()["items"][0]["id"]

    inserted = threading.Event()
    release = threading.Event()
    sent: dict[str, Message] = {}

    client_db = test_session_factory()
    master_db = test_session_factory()
    try:
        # The client's message gets its id first, but its transaction commits only on release.
        client_commit = client_db.commit

        def held_commit() -> None:
            inserted.set()
            assert release.wait(timeout=10)
            client_commit()

        client_db.commit = held_commit

        def send(db, user_id: int, name: str) -> None:
            conversation = db.get(Conversation, conversation_id)
            sender = db.get(User, user_id)
            sent[name] = chat_service.send_message(
                db, conversation, sender, text=name, photo_url=None
            )

        client_sender = threading.Thread(target=send, args=(client_db, owner.user_id, "client"))
        master_sender = threading.Thread(target=send, args=(master_db, master.user_id, "master"))

        client_sender.start()
        assert inserted.wait(timeout=10)
        master_sender.start()

        # The master's message must wait for the client's transaction, so nothing newer than
        # the client's uncommitted message can become visible to a poller first.
        master_sender.join(timeout=1)
        assert master_sender.is_alive()
        polled = client.get(url, headers=master.headers, params={"after": cursor}).json()
        assert polled["items"] == []

        release.set()
        client_sender.join(timeout=10)
        master_sender.join(timeout=10)
        assert not client_sender.is_alive() and not master_sender.is_alive()
    finally:
        release.set()
        client_db.close()
        master_db.close()

    assert sent["client"].id < sent["master"].id
    polled = client.get(url, headers=master.headers, params={"after": cursor}).json()
    assert [item["text"] for item in polled["items"]] == ["client", "master"]


def test_message_must_have_valid_content(client: TestClient, test_session_factory) -> None:
    owner, _, _, _, conversation_id = accepted_chat(client, test_session_factory)
    url = f"/conversations/{conversation_id}/messages"

    for body in (
        {},
        {"text": "   "},
        {"text": None, "photo_url": None},
        {"photo_url": "not-a-url"},
        {"photo_url": "https://cdn.example.com/" + "a" * 500},
        {"text": "x" * 4001},
        {"text": "hi", "sender_id": 1},
    ):
        response = client.post(url, headers=owner.headers, json=body)
        assert response.status_code == 422, (body, response.text)

    photo_only = client.post(
        url,
        headers=owner.headers,
        json={"photo_url": "https://cdn.example.com/a.png"},
    )
    assert photo_only.status_code == 201, photo_only.text
    assert photo_only.json()["text"] is None


def test_only_participants_can_read_and_write(client: TestClient, test_session_factory) -> None:
    _, _, outsider, _, conversation_id = accepted_chat(client, test_session_factory)
    base = f"/conversations/{conversation_id}"

    assert client.get(f"{base}/messages", headers=outsider.headers).status_code == 403
    sent = client.post(f"{base}/messages", headers=outsider.headers, json={"text": "hi"})
    assert sent.status_code == 403
    shown = {"last_read_message_id": 1}
    assert client.post(f"{base}/read", headers=outsider.headers, json=shown).status_code == 403

    listed = client.get("/conversations", headers=outsider.headers).json()
    assert listed == {"items": [], "total": 0, "limit": 20, "offset": 0}

    missing = client.get("/conversations/999999/messages", headers=outsider.headers)
    assert missing.status_code == 404

    assert client.get("/conversations").status_code in (401, 403)


def test_messages_cursor_pagination_and_polling(client: TestClient, test_session_factory) -> None:
    owner, master, _, _, conversation_id = accepted_chat(client, test_session_factory)
    url = f"/conversations/{conversation_id}/messages"

    for number in range(5):
        sender = owner if number % 2 == 0 else master
        response = client.post(url, headers=sender.headers, json={"text": f"message {number}"})
        assert response.status_code == 201, response.text

    # 5 messages + the system message, newest first, two per page.
    collected = []
    cursor = None
    while True:
        params = {"limit": 2} if cursor is None else {"limit": 2, "before": cursor}
        page = client.get(url, headers=owner.headers, params=params).json()
        collected.extend(page["items"])
        cursor = page["next_cursor"]
        if cursor is None:
            break

    ids = [message["id"] for message in collected]
    assert len(ids) == 6
    assert ids == sorted(ids, reverse=True)
    assert collected[-1]["is_system"] is True
    assert collected[0]["text"] == "message 4"

    # Polling: only messages newer than the last one the client has, oldest first.
    newest = ids[0]
    assert client.get(url, headers=owner.headers, params={"after": newest}).json() == {
        "items": [],
        "next_cursor": None,
    }
    newer = client.get(url, headers=owner.headers, params={"after": ids[-1], "limit": 3}).json()
    assert [message["id"] for message in newer["items"]] == sorted(ids)[1:4]
    assert newer["next_cursor"] == sorted(ids)[3]

    both = client.get(url, headers=owner.headers, params={"after": 1, "before": 2})
    assert both.status_code == 422


def test_search_by_name_or_issue_number_and_filter_by_issue(
    client: TestClient,
    test_session_factory,
) -> None:
    with test_session_factory() as db:
        category_id = first_category_id(db)
        owner = create_party(db, "search-owner@example.com", UserRole.CLIENT)
        petrenko, petrenko_id = create_master(db, "petrenko@example.com", "Petrenko")
        shevchuk, shevchuk_id = create_master(db, "shevchuk@example.com", "Shevchuk_100%")
        db.commit()

    first_issue = create_issue(client, owner, category_id, assignee_master_id=petrenko_id)
    second_issue = create_issue(client, owner, category_id, assignee_master_id=shevchuk_id)
    accept(client, first_issue, petrenko)
    accept(client, second_issue, shevchuk)

    def search(**params) -> list[int]:
        response = client.get("/conversations", headers=owner.headers, params=params)
        assert response.status_code == 200, response.text
        return [item["issue"]["id"] for item in response.json()["items"]]

    assert sorted(search()) == sorted([first_issue, second_issue])
    assert search(q="petren") == [first_issue]
    assert search(q="Ivan Shevchuk") == [second_issue]
    assert search(q="100%") == [second_issue]  # % is matched literally
    assert search(q="_") == [second_issue]  # so is _
    assert search(q=f"#{second_issue}") == [second_issue]
    assert search(q=str(first_issue)) == [first_issue]
    assert search(q="nobody") == []
    assert search(issue_id=first_issue) == [first_issue]
    assert search(q="9" * 15) == []


def test_company_issue_chat_is_with_the_master_who_accepted(
    client: TestClient,
    test_session_factory,
) -> None:
    with test_session_factory() as db:
        category_id = first_category_id(db)
        owner = create_party(db, "company-owner@example.com", UserRole.CLIENT)
        company = Company(name="Chat Service Center", type="service_center")
        db.add(company)
        db.flush()
        company_master, _ = create_master(db, "company-master@example.com", "Bondar", company.id)
        company_id = company.id
        db.commit()

    issue_id = create_issue(client, owner, category_id, assignee_company_id=company_id)
    assert client.get("/conversations", headers=owner.headers).json()["total"] == 0

    accept(client, issue_id, company_master)

    items = client.get("/conversations", headers=owner.headers).json()["items"]
    assert len(items) == 1
    assert items[0]["other_party"]["id"] == company_master.user_id
