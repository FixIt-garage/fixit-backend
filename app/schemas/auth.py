from pydantic import BaseModel, EmailStr, Field
from app.models.user import UserRole

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    role: UserRole = UserRole.CLIENT


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class UserResponse(BaseModel):
    id: int
    email: EmailStr
    first_name: str
    last_name: str
    role: UserRole
    is_active: bool

    model_config = {"from_attributes": True}

class MessageResponse(BaseModel):
    message: str
