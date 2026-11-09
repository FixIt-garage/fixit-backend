"""add user profile fields

Revision ID: fc846b9ed8f5
Revises: 968fca11f4b9
Create Date: 2026-11-09 18:35:28.847417

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "fc846b9ed8f5"
down_revision: str | None = "968fca11f4b9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE SEQUENCE users_public_id_seq START 1000")
    op.add_column("users", sa.Column("city", sa.String(length=100), nullable=True))
    op.add_column("users", sa.Column("avatar_url", sa.String(length=500), nullable=True))
    # The default fills public_id for the users that already exist.
    op.add_column(
        "users",
        sa.Column(
            "public_id",
            sa.Integer(),
            server_default=sa.text("nextval('users_public_id_seq')"),
            nullable=False,
        ),
    )
    op.create_unique_constraint("uq_users_public_id", "users", ["public_id"])
    op.create_unique_constraint("uq_users_phone", "users", ["phone"])


def downgrade() -> None:
    op.drop_constraint("uq_users_phone", "users", type_="unique")
    op.drop_constraint("uq_users_public_id", "users", type_="unique")
    op.drop_column("users", "public_id")
    op.drop_column("users", "avatar_url")
    op.drop_column("users", "city")
    op.execute("DROP SEQUENCE IF EXISTS users_public_id_seq")
