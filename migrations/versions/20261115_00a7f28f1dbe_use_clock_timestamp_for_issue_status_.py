"""use clock timestamp for issue status events

Revision ID: 00a7f28f1dbe
Revises: 6215c56724e0
Create Date: 2026-11-15 07:01:15.221715
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "00a7f28f1dbe"
down_revision: str | None = "6215c56724e0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "issue_status_events",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        server_default=sa.text("clock_timestamp()"),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "issue_status_events",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        server_default=sa.text("now()"),
        existing_nullable=False,
    )