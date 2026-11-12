from pydantic import BaseModel, EmailStr

from app.models.user import UserRole


class UserStats(BaseModel):
    requests_count: int
    reviews_count: int
    member_since_year: int


class UserProfileResponse(BaseModel):
    id: int
    public_id: int
    email: EmailStr
    first_name: str
    last_name: str
    phone: str | None
    address: str | None
    city: str | None
    avatar_url: str | None
    role: UserRole
    stats: UserStats
