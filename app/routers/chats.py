from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db import get_db
from app.models.chat import Conversation, Message
from app.models.user import User
from app.schemas.chat import (
    ConversationListRead,
    ConversationReadResult,
    MessageCreate,
    MessagePageRead,
    MessageRead,
)
from app.services import chat as chat_service

router = APIRouter(prefix="/conversations", tags=["Chats"])


def get_participant_conversation(db: Session, conversation_id: int, user: User) -> Conversation:
    """Return the conversation: 404 if it does not exist, 403 if the user is not in it."""
    try:
        return chat_service.get_conversation(db, conversation_id, user)
    except chat_service.ConversationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Conversation not found") from exc
    except chat_service.ConversationPermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.get("", response_model=ConversationListRead)
def list_conversations(
    q: Annotated[
        str | None,
        Query(max_length=100, description="Ім'я співрозмовника або номер заявки"),
    ] = None,
    issue_id: Annotated[int | None, Query(ge=1)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """The user's chats with the other party, issue, last message and unread count."""
    items, total = chat_service.list_conversations(
        db,
        current_user,
        q=q,
        issue_id=issue_id,
        limit=limit,
        offset=offset,
    )
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/{conversation_id}/messages", response_model=MessagePageRead)
def list_messages(
    conversation_id: int,
    before: Annotated[int | None, Query(ge=1, description="Older than this message id")] = None,
    after: Annotated[int | None, Query(ge=0, description="Newer than this message id")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Messages, newest first; `after` returns only newer ones, oldest first (polling)."""
    if before is not None and after is not None:
        raise HTTPException(status_code=422, detail="Use either before or after, not both")

    conversation = get_participant_conversation(db, conversation_id, current_user)
    items, next_cursor = chat_service.list_messages(
        db,
        conversation,
        before=before,
        after=after,
        limit=limit,
    )
    return {"items": items, "next_cursor": next_cursor}


@router.post(
    "/{conversation_id}/messages",
    response_model=MessageRead,
    status_code=status.HTTP_201_CREATED,
)
def send_message(
    conversation_id: int,
    data: MessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Message:
    """Send a text message, a photo, or both."""
    conversation = get_participant_conversation(db, conversation_id, current_user)
    return chat_service.send_message(
        db,
        conversation,
        current_user,
        text=data.text,
        photo_url=str(data.photo_url) if data.photo_url is not None else None,
    )


@router.post("/{conversation_id}/read", response_model=ConversationReadResult)
def mark_read(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark the other participant's messages in this chat as read."""
    conversation = get_participant_conversation(db, conversation_id, current_user)
    return {"marked_read": chat_service.mark_read(db, conversation, current_user)}
