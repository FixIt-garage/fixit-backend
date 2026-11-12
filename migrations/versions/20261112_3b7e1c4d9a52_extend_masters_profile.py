"""extend masters profile

Revision ID: 3b7e1c4d9a52
Revises: fc846b9ed8f5
Create Date: 2026-11-12 18:20:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3b7e1c4d9a52"
down_revision: str | None = "fc846b9ed8f5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("masters", sa.Column("district", sa.String(length=100), nullable=True))
    op.add_column("masters", sa.Column("experience_years", sa.Integer(), nullable=True))
    op.add_column(
        "masters",
        sa.Column("call_out_price", sa.Numeric(precision=10, scale=2), nullable=True),
    )
    op.add_column("masters", sa.Column("schedule", sa.String(length=255), nullable=True))
    op.add_column(
        "masters",
        sa.Column("is_volunteer", sa.Boolean(), server_default="false", nullable=False),
    )
    op.create_table(
        "master_categories",
        sa.Column("master_id", sa.Integer(), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["master_id"], ["masters.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("master_id", "category_id"),
    )
    op.create_index(
        op.f("ix_master_categories_category_id"),
        "master_categories",
        ["category_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_master_categories_category_id"), table_name="master_categories")
    op.drop_table("master_categories")
    op.drop_column("masters", "is_volunteer")
    op.drop_column("masters", "schedule")
    op.drop_column("masters", "call_out_price")
    op.drop_column("masters", "experience_years")
    op.drop_column("masters", "district")