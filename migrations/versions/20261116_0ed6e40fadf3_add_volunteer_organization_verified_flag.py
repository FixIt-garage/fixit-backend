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
    # One organization per owner is new. Stop before changing anything if the data breaks it:
    # which organization to keep, and where their volunteer requests go, is a decision for people.
    duplicates = (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT owner_user_id FROM volunteer_organizations "
                "GROUP BY owner_user_id HAVING count(*) > 1"
            )
        )
        .scalars()
        .all()
    )
    if duplicates:
        raise RuntimeError(
            f"{len(duplicates)} user(s) own more than one volunteer organization "
            f"(owner_user_id: {duplicates}). Resolve them by hand, keeping the volunteer "
            "requests (volunteer_requests.organization_id) of every organization, then run "
            "the migration again. Nothing was changed."
        )

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
