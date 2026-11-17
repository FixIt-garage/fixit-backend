from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator

from app.models.issue import IssueStatus

MESSAGE_TEXT_MAX_LENGTH = 4000
PHOTO_URL_MAX_LENGTH = 500


class MessageCreate(BaseModel):
    """A text message, a photo, or both. The photo is a URL of an already uploaded file."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    text: str | None = Field(None, max_length=MESSAGE_TEXT_MAX_LENGTH, description="Текст")
    photo_url: HttpUrl | None = Field(None, description="URL завантаженого фото")

    @field_validator("text")
    @classmethod
    def empty_text_is_none(cls, value: str | None) -> str | None:
        return value or None

    @field_validator("photo_url")
    @classmethod
    def photo_url_fits_column(cls, value: HttpUrl | None) -> HttpUrl | None:
        if value is not None and len(str(value)) > PHOTO_URL_MAX_LENGTH:
            raise ValueError(f"photo_url must be at most {PHOTO_URL_MAX_LENGTH} characters")
        return value

    @model_validator(mode="after")
    def has_content(self) -> "MessageCreate":
        if self.text is None and self.photo_url is None:
            raise ValueError("Message must have text or a photo")
        return self


class MessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    conversation_id: int
    sender_id: int | None
    text: str | None
    photo_url: str | None
    is_system: bool
    created_at: datetime
    read_at: datetime | None


class MessagePageRead(BaseModel):
    items: list[MessageRead]
    # Pass as `before` (or `after` when polling) to get the next page; null when there is none.
    next_cursor: int | None


class ConversationParticipantRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    first_name: str
    last_name: str
    avatar_url: str | None


class ConversationIssueRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    status: IssueStatus


class ConversationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    issue: ConversationIssueRead
    other_party: ConversationParticipantRead
    last_message: MessageRead | None
    last_message_at: datetime | None
    unread_count: int


class ConversationListRead(BaseModel):
    items: list[ConversationRead]
    total: int
    limit: int
    offset: int


class ConversationReadResult(BaseModel):
    marked_read: int
