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


def _delete_unused(conn, slugs: list[str]) -> None:
    """Delete seeded categories that no service references."""
    stmt = sa.text(
        "DELETE FROM categories WHERE slug IN :slugs "
        "AND NOT EXISTS (SELECT 1 FROM services WHERE services.category_id = categories.id)"
    ).bindparams(sa.bindparam("slugs", expanding=True))
    conn.execute(stmt, {"slugs": slugs})


def upgrade() -> None:
    conn = op.get_bind()
    ids = {slug: _upsert(conn, name, slug, None, order) for name, slug, order in ROOTS}
    for name, slug, parent_slug, order in CHILDREN:
        _upsert(conn, name, slug, ids[parent_slug], order)


def downgrade() -> None:
    conn = op.get_bind()
    _delete_unused(conn, CHILD_SLUGS)
    conn.execute(
        categories.update().where(categories.c.slug.in_(CHILD_SLUGS)).values(parent_id=None)
    )
    _delete_unused(conn, ROOT_SLUGS)
    # Categories still used by services stay, but lose the seeded fields.
    conn.execute(
        categories.update()
        .where(categories.c.slug.in_(ROOT_SLUGS + CHILD_SLUGS))
        .values(slug=None, name_uk=None, sort_order=0)
    )
