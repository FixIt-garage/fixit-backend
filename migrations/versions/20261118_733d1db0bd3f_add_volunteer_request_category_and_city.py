"""add volunteer request category and city

Revision ID: 733d1db0bd3f
Revises: 0ed6e40fadf3
Create Date: 2026-11-18 22:11:24.607561

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '733d1db0bd3f'
down_revision: str | None = '0ed6e40fadf3'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("volunteer_requests", sa.Column("category_id", sa.Integer(), nullable=True))
    op.add_column("volunteer_requests", sa.Column("city", sa.String(length=100), nullable=True))
    op.create_index(
        op.f("ix_volunteer_requests_category_id"),
        "volunteer_requests",
        ["category_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_volunteer_requests_city"), "volunteer_requests", ["city"], unique=False
    )
    op.create_foreign_key(
        "fk_volunteer_requests_category_id_categories",
        "volunteer_requests",
        "categories",
        ["category_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_volunteer_requests_category_id_categories", "volunteer_requests", type_="foreignkey"
    )
    op.drop_index(op.f("ix_volunteer_requests_city"), table_name="volunteer_requests")
    op.drop_index(op.f("ix_volunteer_requests_category_id"), table_name="volunteer_requests")
    op.drop_column("volunteer_requests", "city")
    op.drop_column("volunteer_requests", "category_id")
