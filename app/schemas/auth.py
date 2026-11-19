from pydantic import EmailStr, Field

from app.models.user import UserRole
from app.schemas.base import BaseSchema, RequestSchema
from app.schemas.validators import Address, Email, LoginEmail, Phone


class RegisterRequest(RequestSchema):
    email: Email
    password: str = Field(min_length=8, max_length=128)
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    phone: Phone | None = None
    address: Address | None = None
    role: UserRole = UserRole.CLIENT


class LoginRequest(RequestSchema):
    email: LoginEmail
    password: str


class RefreshRequest(RequestSchema):
    refresh_token: str


class TokenResponse(BaseSchema):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserResponse(BaseSchema):
    id: int
    email: EmailStr
    first_name: str
    last_name: str
    phone: str | None = None
    address: str | None = None
    role: UserRole
    is_active: bool


class MessageResponse(BaseSchema):
    message: str