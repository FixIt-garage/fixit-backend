"""add service center profiles

Revision ID: 232d55a844e1
Revises: 5571b786cd03
Create Date: 2026-11-15 14:47:55.915141
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "232d55a844e1"
down_revision: str | None = "5571b786cd03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Generate public IDs for service centers.
    op.execute(sa.schema.CreateSequence(sa.Sequence("companies_public_id_seq", start=1000)))

    op.add_column(
        "companies",
        sa.Column("public_id", sa.Integer(), nullable=True),
    )

    op.execute(
        """
        ALTER TABLE companies
        ALTER COLUMN public_id
        SET DEFAULT nextval('companies_public_id_seq')
        """
    )

    op.execute(
        """
        ALTER SEQUENCE companies_public_id_seq
        OWNED BY companies.public_id
        """
    )

    op.execute(
        """
        UPDATE companies
        SET public_id = nextval('companies_public_id_seq')
        WHERE public_id IS NULL
        """
    )

    op.alter_column(
        "companies",
        "public_id",
        existing_type=sa.Integer(),
        nullable=False,
    )

    op.create_unique_constraint(
        "companies_public_id_key",
        "companies",
        ["public_id"],
    )

    # Service center owner and contact information.
    op.add_column(
        "companies",
        sa.Column("owner_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "companies",
        sa.Column("latitude", sa.Numeric(9, 6), nullable=True),
    )
    op.add_column(
        "companies",
        sa.Column("longitude", sa.Numeric(9, 6), nullable=True),
    )
    op.add_column(
        "companies",
        sa.Column("phone", sa.String(32), nullable=True),
    )
    op.add_column(
        "companies",
        sa.Column("opening_hours", sa.JSON(), nullable=True),
    )

    op.create_foreign_key(
        "fk_companies_owner_id_users",
        "companies",
        "users",
        ["owner_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_companies_owner_id",
        "companies",
        ["owner_id"],
    )

    # Service center categories.
    op.create_table(
        "company_categories",
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name="fk_company_categories_company_id_companies",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["categories.id"],
            name="fk_company_categories_category_id_categories",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "company_id",
            "category_id",
            name="pk_company_categories",
        ),
    )

    op.create_index(
        "ix_company_categories_category_id",
        "company_categories",
        ["category_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_company_categories_category_id",
        table_name="company_categories",
    )
    op.drop_table("company_categories")

    op.drop_index("ix_companies_owner_id", table_name="companies")
    op.drop_constraint(
        "fk_companies_owner_id_users",
        "companies",
        type_="foreignkey",
    )

    op.drop_column("companies", "opening_hours")
    op.drop_column("companies", "phone")
    op.drop_column("companies", "longitude")
    op.drop_column("companies", "latitude")
    op.drop_column("companies", "owner_id")

    op.drop_constraint(
        "companies_public_id_key",
        "companies",
        type_="unique",
    )
    op.drop_column("companies", "public_id")
