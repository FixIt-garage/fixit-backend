"""seed repair categories from Figma

Revision ID: a7c91d5e3b20
Revises: e3b46f671fc0
Create Date: 2026-11-03 15:10:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a7c91d5e3b20"
down_revision: str | None = "e3b46f671fc0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

categories = sa.table(
    "categories",
    sa.column("id", sa.Integer),
    sa.column("name", sa.String),
    sa.column("slug", sa.String),
    sa.column("name_uk", sa.String),
    sa.column("parent_id", sa.Integer),
    sa.column("sort_order", sa.Integer),
)

# (name, slug, sort_order)
ROOTS = [
    ("Побутова техніка", "appliances", 1),
    ("Електрика", "electrics", 2),
    ("Сантехніка", "plumbing", 3),
    ("Смартфони", "smartphones", 4),
    ("Меблі", "furniture", 5),
]
# (name, slug, parent slug, sort_order within the parent)
CHILDREN = [
    ("Пральні машини", "washing-machines", "appliances", 1),
    ("Холодильники", "refrigerators", "appliances", 2),
]
ROOT_SLUGS = [slug for _, slug, _ in ROOTS]
CHILD_SLUGS = [slug for _, slug, _, _ in CHILDREN]


def _upsert(conn, name: str, slug: str, parent_id: int | None, sort_order: int) -> int:
    """Fill an existing category (found by name, its id is kept) or insert a new one."""
    values = {
        "slug": slug,
        "name_uk": name,
        "parent_id": parent_id,
        "sort_order": sort_order,
    }
    stmt = categories.update().where(categories.c.name == name).values(**values)
    if conn.execute(stmt).rowcount == 0:
        conn.execute(categories.insert().values(name=name, **values))
    query = sa.select(categories.c.id).where(categories.c.slug == slug)
    return conn.execute(query).scalar_one()


def upgrade() -> None:
    conn = op.get_bind()
    ids = {slug: _upsert(conn, name, slug, None, order) for name, slug, order in ROOTS}
    for name, slug, parent_slug, order in CHILDREN:
        _upsert(conn, name, slug, ids[parent_slug], order)


def downgrade() -> None:
    # Conservative on purpose: nothing is deleted. Rows that existed before this migration
    # (matched by name) and rows created by it all stay, so ids, services and child
    # categories are never lost and ON DELETE RESTRICT cannot make the rollback fail.
    # Only the fields filled by the seed are cleared.
    conn = op.get_bind()
    conn.execute(
        categories.update()
        .where(categories.c.slug.in_(ROOT_SLUGS + CHILD_SLUGS))
        .values(slug=None, name_uk=None, parent_id=None, sort_order=0)
    )
