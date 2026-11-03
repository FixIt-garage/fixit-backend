"""extend categories with slug, name_uk, parent, sort_order

Revision ID: e3b46f671fc0
Revises: 4c02736053a1
Create Date: 2026-11-02 19:16:00.273448

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e3b46f671fc0"
down_revision: str | None = "4c02736053a1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("categories", sa.Column("slug", sa.String(length=100), nullable=True))
    op.add_column("categories", sa.Column("name_uk", sa.String(length=150), nullable=True))
    op.add_column("categories", sa.Column("parent_id", sa.Integer(), nullable=True))
    op.add_column(
        "categories",
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
    )
    op.create_index(op.f("ix_categories_parent_id"), "categories", ["parent_id"], unique=False)
    op.create_unique_constraint("uq_categories_slug", "categories", ["slug"])
    op.create_foreign_key(
        "fk_categories_parent_id_categories",
        "categories",
        "categories",
        ["parent_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint("fk_categories_parent_id_categories", "categories", type_="foreignkey")
    op.drop_constraint("uq_categories_slug", "categories", type_="unique")
    op.drop_index(op.f("ix_categories_parent_id"), table_name="categories")
    op.drop_column("categories", "sort_order")
    op.drop_column("categories", "parent_id")
    op.drop_column("categories", "name_uk")
    op.drop_column("categories", "slug")
