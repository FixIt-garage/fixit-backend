
"""Add authentication fields to users."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f8ecb1036057"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

user_role = postgresql.ENUM(
    "client",
    "master",
    "service_center",
    "volunteer_organization",
    name="user_role",
)


def upgrade() -> None:
    """Add role, account status and update timestamp to users."""
    user_role.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "users",
        sa.Column(
            "role",
            user_role,
            server_default="client",
            nullable=False,
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.true(),
            nullable=False,
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    """Remove authentication fields from users."""
    op.drop_column("users", "updated_at")
    op.drop_column("users", "is_active")
    op.drop_column("users", "role")

    user_role.drop(op.get_bind(), checkfirst=True)
