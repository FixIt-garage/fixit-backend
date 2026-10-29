from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.category import Category


def list_categories(db: Session) -> list[Category]:
    stmt = select(Category).order_by(Category.sort_order, Category.id)
    return list(db.scalars(stmt))
