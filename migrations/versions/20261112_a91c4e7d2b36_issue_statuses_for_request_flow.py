"""align issue statuses with the request flow

Revision ID: a91c4e7d2b36
Revises: 3b7e1c4d9a52
Create Date: 2026-11-12 20:10:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a91c4e7d2b36"
down_revision: str | None = "3b7e1c4d9a52"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # A value cannot be removed from a PostgreSQL enum, so the type is replaced:
    # rename the old type, create the new one, convert the column (old values are
    # mapped to the new ones), then drop the old type.
    op.execute("ALTER TYPE issuestatus RENAME TO issuestatus_old")
    op.execute(
        "CREATE TYPE issuestatus AS ENUM "
        "('sent', 'accepted', 'in_progress', 'done', 'declined', 'cancelled')"
    )
    op.execute(
        """
        ALTER TABLE issues ALTER COLUMN status TYPE issuestatus USING (
            CAST(
                CASE CAST(status AS text)
                    WHEN 'OPEN' THEN 'sent'
                    WHEN 'IN_PROGRESS' THEN 'in_progress'
                    WHEN 'RESOLVED' THEN 'done'
                    WHEN 'CLOSED' THEN 'cancelled'
                END AS issuestatus
            )
        )
        """
    )
    op.execute("DROP TYPE issuestatus_old")


def downgrade() -> None:
    # Lossy: accepted and in_progress both become IN_PROGRESS,
    # declined and cancelled both become CLOSED.
    op.execute("ALTER TYPE issuestatus RENAME TO issuestatus_new")
    op.execute("CREATE TYPE issuestatus AS ENUM ('OPEN', 'IN_PROGRESS', 'RESOLVED', 'CLOSED')")
    op.execute(
        """
        ALTER TABLE issues ALTER COLUMN status TYPE issuestatus USING (
            CAST(
                CASE CAST(status AS text)
                    WHEN 'sent' THEN 'OPEN'
                    WHEN 'accepted' THEN 'IN_PROGRESS'
                    WHEN 'in_progress' THEN 'IN_PROGRESS'
                    WHEN 'done' THEN 'RESOLVED'
                    WHEN 'declined' THEN 'CLOSED'
                    WHEN 'cancelled' THEN 'CLOSED'
                END AS issuestatus
            )
        )
        """
    )
    op.execute("DROP TYPE issuestatus_new")