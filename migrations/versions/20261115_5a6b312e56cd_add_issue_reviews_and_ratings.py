"""add issue reviews and ratings

Revision ID: 5a6b312e56cd
Revises: 00a7f28f1dbe
Create Date: 2026-11-15 08:28:13.962162
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "5a6b312e56cd"
down_revision: str | None = "00a7f28f1dbe"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Legacy order reviews cannot be safely mapped to the new issue model.
    bind = op.get_bind()
    legacy_review_count = bind.execute(
        sa.text("SELECT COUNT(*) FROM reviews")
    ).scalar_one()

    if legacy_review_count:
        raise RuntimeError(
            f"Cannot migrate reviews: found {legacy_review_count} legacy "
            "order reviews that cannot be mapped to issues."
        )

    # Cached ratings for service centers and review counts.
    op.add_column(
        "companies",
        sa.Column("rating", sa.Numeric(precision=3, scale=2), nullable=True),
    )
    op.add_column(
        "companies",
        sa.Column(
            "reviews_count",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
    )
    op.add_column(
        "masters",
        sa.Column(
            "reviews_count",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
    )

    # Preserve the original service center assigned to an issue.
    op.add_column(
        "issues",
        sa.Column("review_company_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_issues_review_company_id_companies",
        "issues",
        "companies",
        ["review_company_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.execute(
        "UPDATE issues "
        "SET review_company_id = assignee_company_id "
        "WHERE assignee_company_id IS NOT NULL"
    )

    # New review structure. The old reviews table is empty.
    op.add_column("reviews", sa.Column("issue_id", sa.Integer(), nullable=False))
    op.add_column("reviews", sa.Column("author_id", sa.Integer(), nullable=False))
    op.add_column("reviews", sa.Column("master_id", sa.Integer(), nullable=True))
    op.add_column("reviews", sa.Column("company_id", sa.Integer(), nullable=True))
    op.add_column("reviews", sa.Column("tags", sa.JSON(), nullable=False))
    op.add_column("reviews", sa.Column("comment", sa.Text(), nullable=True))

    # Replace the old order relationship with the issue relationship.
    op.drop_constraint("reviews_order_id_key", "reviews", type_="unique")
    op.drop_constraint("reviews_order_id_fkey", "reviews", type_="foreignkey")

    op.drop_column("reviews", "order_id")
    op.drop_column("reviews", "title")
    op.drop_column("reviews", "description")

    op.create_foreign_key(
        "fk_reviews_issue_id_issues",
        "reviews",
        "issues",
        ["issue_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_reviews_author_id_users",
        "reviews",
        "users",
        ["author_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_reviews_master_id_masters",
        "reviews",
        "masters",
        ["master_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_reviews_company_id_companies",
        "reviews",
        "companies",
        ["company_id"],
        ["id"],
    )

    op.create_unique_constraint(
        "uq_reviews_issue_id",
        "reviews",
        ["issue_id"],
    )
    op.create_check_constraint(
        "ck_reviews_exactly_one_target",
        "reviews",
        """
        (master_id IS NOT NULL AND company_id IS NULL)
        OR
        (master_id IS NULL AND company_id IS NOT NULL)
        """,
    )


def downgrade() -> None:
    # An issue review cannot be mapped back to an old order review.
    # Refuse the downgrade rather than silently losing review data.
    bind = op.get_bind()
    review_count = bind.execute(
        sa.text("SELECT COUNT(*) FROM reviews")
    ).scalar_one()

    if review_count:
        raise RuntimeError(
            "Cannot downgrade: reviews exist and cannot be mapped "
            "back to legacy orders."
        )

    op.drop_constraint(
        "ck_reviews_exactly_one_target",
        "reviews",
        type_="check",
    )
    op.drop_constraint("uq_reviews_issue_id", "reviews", type_="unique")

    op.drop_constraint(
        "fk_reviews_company_id_companies",
        "reviews",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_reviews_master_id_masters",
        "reviews",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_reviews_author_id_users",
        "reviews",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_reviews_issue_id_issues",
        "reviews",
        type_="foreignkey",
    )

    op.add_column(
        "reviews",
        sa.Column("order_id", sa.Integer(), nullable=False),
    )
    op.add_column(
        "reviews",
        sa.Column("title", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "reviews",
        sa.Column("description", sa.Text(), nullable=True),
    )

    op.create_foreign_key(
        "reviews_order_id_fkey",
        "reviews",
        "orders",
        ["order_id"],
        ["id"],
    )
    op.create_unique_constraint(
        "reviews_order_id_key",
        "reviews",
        ["order_id"],
    )

    op.drop_column("reviews", "comment")
    op.drop_column("reviews", "tags")
    op.drop_column("reviews", "company_id")
    op.drop_column("reviews", "master_id")
    op.drop_column("reviews", "author_id")
    op.drop_column("reviews", "issue_id")

    op.drop_constraint(
        "fk_issues_review_company_id_companies",
        "issues",
        type_="foreignkey",
    )
    op.drop_column("issues", "review_company_id")

    op.drop_column("masters", "reviews_count")
    op.drop_column("companies", "reviews_count")
    op.drop_column("companies", "rating")
