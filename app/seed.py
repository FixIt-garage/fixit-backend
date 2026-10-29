"""Dev seed data (placeholder).

Run inside the compose stack:  docker compose exec backend python -m app.seed
Safe to run several times: rows that already exist are skipped.
"""

from app.db import SessionLocal
from app.models import Category, Service

SEED: dict[str, list[str]] = {
    "Електрика": ["Заміна розетки", "Ремонт пральних машин"],
    "Сантехніка": ["Чистка унітазу", "Заміна змішувача"],
}


def run() -> None:
    with SessionLocal() as db:
        for category_name, service_names in SEED.items():
            category = db.query(Category).filter_by(name=category_name).one_or_none()
            if category is None:
                category = Category(name=category_name)
                db.add(category)
                db.flush()
            for service_name in service_names:
                exists = (
                    db.query(Service)
                    .filter_by(category_id=category.id, name=service_name)
                    .one_or_none()
                )
                if exists is None:
                    db.add(Service(category_id=category.id, name=service_name))
        db.commit()
    print("Seed done.")


if __name__ == "__main__":
    run()
