"""add issue assignees and status events

Revision ID: 35098736a657
Revises: a91c4e7d2b36
Create Date: 2026-11-14 20:11:58.298438
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "35098736a657"
down_revision: str | None = "a91c4e7d2b36"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "issue_status_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("issue_id", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "sent",
                "accepted",
                "in_progress",
                "done",
                "declined",
                "cancelled",
                name="issuestatus",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("actor_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["users.id"],
            name="fk_issue_status_events_actor_id_users",
        ),
        sa.ForeignKeyConstraint(
            ["issue_id"],
            ["issues.id"],
            name="fk_issue_status_events_issue_id_issues",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_issue_status_events_actor_id",
        "issue_status_events",
        ["actor_id"],
        unique=False,
    )
    op.create_index(
        "ix_issue_status_events_issue_id",
        "issue_status_events",
        ["issue_id"],
        unique=False,
    )

    op.add_column(
        "issues",
        sa.Column("assignee_master_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "issues",
        sa.Column("assignee_company_id", sa.Integer(), nullable=True),
    )

    op.create_index(
        "ix_issues_assignee_company_id",
        "issues",
        ["assignee_company_id"],
        unique=False,
    )
    op.create_index(
        "ix_issues_assignee_master_id",
        "issues",
        ["assignee_master_id"],
        unique=False,
    )

    op.create_foreign_key(
        "fk_issues_assignee_company_id_companies",
        "issues",
        "companies",
        ["assignee_company_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_issues_assignee_master_id_masters",
        "issues",
        "masters",
        ["assignee_master_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_check_constraint(
        "ck_issues_single_assignee",
        "issues",
        "assignee_master_id IS NULL OR assignee_company_id IS NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_issues_single_assignee",
        "issues",
        type_="check",
    )

    op.drop_constraint(
        "fk_issues_assignee_master_id_masters",
        "issues",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_issues_assignee_company_id_companies",
        "issues",
        type_="foreignkey",
    )

    op.drop_index("ix_issues_assignee_master_id", table_name="issues")
    op.drop_index("ix_issues_assignee_company_id", table_name="issues")

    op.drop_column("issues", "assignee_company_id")
    op.drop_column("issues", "assignee_master_id")

    op.drop_index(
        "ix_issue_status_events_issue_id",
        table_name="issue_status_events",
    )
    op.drop_index(
        "ix_issue_status_events_actor_id",
        table_name="issue_status_events",
    )
    op.drop_table("issue_status_events")
