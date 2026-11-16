"""add volunteer organization verified flag

Revision ID: 0ed6e40fadf3
Revises: 232d55a844e1
Create Date: 2026-11-16 22:08:57.988314

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0ed6e40fadf3'
down_revision: str | None = '232d55a844e1'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "volunteer_organizations",
        sa.Column("is_verified", sa.Boolean(), server_default="false", nullable=False),
    )
    op.create_unique_constraint(
        "uq_volunteer_organizations_owner_user_id",
        "volunteer_organizations",
        ["owner_user_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_volunteer_organizations_owner_user_id",
        "volunteer_organizations",
        type_="unique",
    )
    op.drop_column("volunteer_organizations", "is_verified")
