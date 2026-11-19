"""add uploads

Revision ID: c8e2f4a1b7d3
Revises: 733d1db0bd3f
Create Date: 2026-11-19 20:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c8e2f4a1b7d3"
down_revision: str | None = "733d1db0bd3f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

upload_kind = sa.Enum("avatar", "chat", name="upload_kind")


def upgrade() -> None:
    op.create_table(
        "uploads",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "owner_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", upload_kind, nullable=False),
        sa.Column("path", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=50), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("path", name="uq_uploads_path"),
    )
    op.create_index("ix_uploads_owner_id", "uploads", ["owner_id"])


def downgrade() -> None:
    op.drop_index("ix_uploads_owner_id", table_name="uploads")
    op.drop_table("uploads")
    upload_kind.drop(op.get_bind(), checkfirst=True)