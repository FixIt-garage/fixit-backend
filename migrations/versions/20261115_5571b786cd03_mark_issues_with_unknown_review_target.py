"""Mark issues with unknown review target

Revision ID: 5571b786cd03
Revises: 5a6b312e56cd
Create Date: 2026-11-15 11:15:33.710176

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '5571b786cd03'
down_revision: str | None = '5a6b312e56cd'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

def upgrade() -> None:
    op.add_column(
        "issues",
        sa.Column(
            "review_target_unknown",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
    )

    op.execute(
        """
        UPDATE issues
        SET review_target_unknown = TRUE
        WHERE assignee_master_id IS NOT NULL
          AND assignee_company_id IS NULL
          AND review_company_id IS NULL
        """
    )


def downgrade() -> None:
    op.drop_column("issues", "review_target_unknown")