"""All models, imported here so `Base.metadata` sees every table (used by Alembic)."""

from app.models.base import Base
from app.models.catalog import Category, Service
from app.models.company import Company, CompanyCategory, CompanyService
from app.models.issue import Issue, IssueStatus
from app.models.issue_status_event import IssueStatusEvent
from app.models.master import Master, MasterCategory, MasterService
from app.models.order import Order, OrderStatus
from app.models.refresh_token import RefreshToken
from app.models.review import Review
from app.models.upload import Upload, UploadKind
from app.models.user import User
from app.models.volunteer import (
    VolunteerOrganization,
    VolunteerParticipation,
    VolunteerRequest,
    VolunteerRequestStatus,
)

__all__ = [
    "Base",
    "Category",
    "Company",
    "CompanyCategory",
    "CompanyService",
    "Issue",
    "IssueStatus",
    "IssueStatusEvent",
    "Master",
    "MasterCategory",
    "MasterService",
    "Order",
    "OrderStatus",
    "RefreshToken",
    "Review",
    "Service",
    "Upload",
    "UploadKind",
    "User",
    "VolunteerOrganization",
    "VolunteerParticipation",
    "VolunteerRequest",
    "VolunteerRequestStatus",
]
