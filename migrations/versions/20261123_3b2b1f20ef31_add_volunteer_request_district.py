"""add volunteer request district

Revision ID: 3b2b1f20ef31
Revises: ae86550452ca
Create Date: 2026-11-23 20:34:19.508925

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '3b2b1f20ef31'
down_revision: str | None = 'ae86550452ca'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "volunteer_requests", sa.Column("district", sa.String(length=100), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("volunteer_requests", "district")
