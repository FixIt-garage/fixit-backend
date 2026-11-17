"""Chats between a client and the master who accepted the client's issue.

Live delivery for the MVP is polling: the list (`GET /conversations`) carries unread counts,
and `GET /conversations/{id}/messages?after=<last id>` returns only new messages.
"""

import re
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import case, false, func, or_, select, update
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.orm import Session

from app.models.chat import Conversation, Message
from app.models.issue import Issue
from app.models.user import User

ISSUE_ACCEPTED_TEXT = "Майстер прийняв заявку"


class ConversationNotFoundError(Exception):
    """Raised when a conversation does not exist (or its issue was deleted)."""


class ConversationPermissionError(Exception):
    """Raised when a user is not a participant of the conversation."""


@dataclass
class ConversationSummary:
    id: int
    issue: Issue
    other_party: User
    last_message: Message | None
    last_message_at: datetime | None
    unread_count: int


def _add_message(db: Session, conversation: Conversation, message: Message) -> Message:
    """Store a message and move the conversation's last-message time to it."""
    db.add(message)
    db.flush()
    db.refresh(message)
    conversation.last_message_at = message.created_at
    return message


def open_conversation(db: Session, issue: Issue, master_user_id: int) -> Conversation:
    """Return the issue's conversation, creating it with a system message (no commit)."""
    conversation = db.scalar(select(Conversation).where(Conversation.issue_id == issue.id))
    if conversation is not None:
        return conversation

    conversation = Conversation(
        issue_id=issue.id,
        client_id=issue.owner_id,
        master_user_id=master_user_id,
    )
    db.add(conversation)
    db.flush()

    _add_message(
        db,
        conversation,
        Message(conversation_id=conversation.id, is_system=True, text=ISSUE_ACCEPTED_TEXT),
    )
    return conversation


def get_conversation(db: Session, conversation_id: int, user: User) -> Conversation:
    """Return a conversation the user takes part in: 404 if missing, 403 if not a participant."""
    conversation = db.scalar(
        select(Conversation)
        .join(Issue, Issue.id == Conversation.issue_id)
        .where(Conversation.id == conversation_id, Issue.deleted_at.is_(None))
    )
    if conversation is None:
        raise ConversationNotFoundError(conversation_id)
    if user.id not in (conversation.client_id, conversation.master_user_id):
        raise ConversationPermissionError("Not a participant of this conversation")
    return conversation


def _escape_like(value: str) -> str:
    return re.sub(r"([\\%_])", r"\\\1", value)


def list_conversations(
    db: Session,
    user: User,
    *,
    q: str | None = None,
    issue_id: int | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[ConversationSummary], int]:
    """The user's conversations, newest activity first, with last message and unread count."""
    other_party_id = case(
        (Conversation.client_id == user.id, Conversation.master_user_id),
        else_=Conversation.client_id,
    )
    stmt = (
        select(Conversation, Issue, User)
        .join(Issue, Issue.id == Conversation.issue_id)
        .join(User, User.id == other_party_id)
        .where(
            or_(Conversation.client_id == user.id, Conversation.master_user_id == user.id),
            Issue.deleted_at.is_(None),
        )
    )

    if issue_id is not None:
        stmt = stmt.where(Conversation.issue_id == issue_id)

    query = (q or "").strip()
    number = query.lstrip("#")
    if number.isdigit():
        # A request number such as "1240" or "#1240" (ids above the int range match nothing).
        stmt = stmt.where(Issue.id == int(number)) if len(number) <= 9 else stmt.where(false())
    elif query:
        pattern = f"%{_escape_like(query)}%"
        stmt = stmt.where(
            or_(
                User.first_name.ilike(pattern, escape="\\"),
                User.last_name.ilike(pattern, escape="\\"),
                func.concat(User.first_name, " ", User.last_name).ilike(pattern, escape="\\"),
            )
        )

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0

    rows = db.execute(
        stmt.order_by(
            Conversation.last_message_at.desc().nulls_last(),
            Conversation.id.desc(),
        )
        .limit(limit)
        .offset(offset)
    ).all()

    conversation_ids = [conversation.id for conversation, _, _ in rows]
    last_messages: dict[int, Message] = {}
    unread_counts: dict[int, int] = {}

    if conversation_ids:
        last_messages = {
            message.conversation_id: message
            for message in db.scalars(
                select(Message)
                .where(Message.conversation_id.in_(conversation_ids))
                .ext(distinct_on(Message.conversation_id))
                .order_by(Message.conversation_id, Message.id.desc())
            )
        }
        unread_counts = dict(
            db.execute(
                select(Message.conversation_id, func.count())
                .where(
                    Message.conversation_id.in_(conversation_ids),
                    Message.is_system.is_(False),
                    Message.sender_id != user.id,
                    Message.read_at.is_(None),
                )
                .group_by(Message.conversation_id)
            ).all()
        )

    items = [
        ConversationSummary(
            id=conversation.id,
            issue=issue,
            other_party=other_party,
            last_message=last_messages.get(conversation.id),
            last_message_at=conversation.last_message_at,
            unread_count=unread_counts.get(conversation.id, 0),
        )
        for conversation, issue, other_party in rows
    ]
    return items, total


def list_messages(
    db: Session,
    conversation: Conversation,
    *,
    before: int | None = None,
    after: int | None = None,
    limit: int = 50,
) -> tuple[list[Message], int | None]:
    """A page of messages and the cursor for the next one.

    Default and `before=<id>`: newest first, scrolling back in history.
    `after=<id>`: oldest first, only messages newer than the id (for polling).
    """
    stmt = select(Message).where(Message.conversation_id == conversation.id)

    if after is not None:
        stmt = stmt.where(Message.id > after).order_by(Message.id.asc())
    else:
        if before is not None:
            stmt = stmt.where(Message.id < before)
        stmt = stmt.order_by(Message.id.desc())

    messages = list(db.scalars(stmt.limit(limit + 1)))
    has_more = len(messages) > limit
    messages = messages[:limit]
    next_cursor = messages[-1].id if has_more and messages else None
    return messages, next_cursor


def send_message(
    db: Session,
    conversation: Conversation,
    sender: User,
    *,
    text: str | None,
    photo_url: str | None,
) -> Message:
    """Add a participant's message to the conversation."""
    message = _add_message(
        db,
        conversation,
        Message(
            conversation_id=conversation.id,
            sender_id=sender.id,
            text=text,
            photo_url=photo_url,
        ),
    )
    db.commit()
    db.refresh(message)
    return message


def mark_read(db: Session, conversation: Conversation, reader: User) -> int:
    """Mark the other participant's unread messages as read; return how many were marked."""
    result = db.execute(
        update(Message)
        .where(
            Message.conversation_id == conversation.id,
            Message.is_system.is_(False),
            Message.sender_id != reader.id,
            Message.read_at.is_(None),
        )
        .values(read_at=func.clock_timestamp())
    )
    db.commit()
    return result.rowcount or 0
