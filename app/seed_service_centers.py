"""Create or update a service center for an existing owner.

Example:
    python -m app.seed_service_centers \
        --owner-email center@example.com \
        --name "FixIt Service Center" \
        --address "Lviv, Ukraine" \
        --phone "+380501234567"
"""

import argparse
import json
from decimal import Decimal

from sqlalchemy import select

from app.db import SessionLocal
from app.models.catalog import Category, Service
from app.models.company import Company
from app.models.user import User, UserRole
from app.schemas.service_center import OpeningHours


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create or update a service center.")

    parser.add_argument("--owner-email", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--address")
    parser.add_argument("--phone")
    parser.add_argument("--latitude", type=Decimal)
    parser.add_argument("--longitude", type=Decimal)
    parser.add_argument(
        "--opening-hours",
        help='JSON, e.g. {"monday":{"open":"09:00","close":"18:00"}}',
    )
    parser.add_argument("--category-ids", nargs="*", type=int)
    parser.add_argument("--service-ids", nargs="*", type=int)

    return parser.parse_args()


def load_items(db, model, item_ids: list[int], field_name: str):
    if len(item_ids) != len(set(item_ids)):
        raise ValueError(f"{field_name} must not contain duplicate IDs")

    items = db.scalars(select(model).where(model.id.in_(item_ids))).all()

    if len(items) != len(item_ids):
        raise ValueError(f"Some {field_name} do not exist")

    return items


def run(args: argparse.Namespace) -> None:
    if (args.latitude is None) != (args.longitude is None):
        raise ValueError("Latitude and longitude must be provided together")

    opening_hours = None
    if args.opening_hours is not None:
        try:
            opening_hours = OpeningHours.model_validate(json.loads(args.opening_hours)).model_dump(
                exclude_unset=True, mode="json"
            )
        except (json.JSONDecodeError, ValueError) as exc:
            raise ValueError(f"Invalid opening hours: {exc}") from exc

    with SessionLocal() as db:
        owner = db.scalar(select(User).where(User.email == args.owner_email))

        if owner is None:
            raise ValueError("Owner with this email does not exist")

        if owner.role != UserRole.SERVICE_CENTER:
            raise ValueError("Owner must have the service_center role")

        centers = db.scalars(
            select(Company).where(
                Company.owner_id == owner.id,
                Company.type == "service_center",
            )
        ).all()

        if len(centers) > 1:
            raise ValueError(
                "Owner has multiple service centers. Update the intended center manually."
            )

        if centers:
            center = centers[0]
            action = "updated"
        else:
            center = Company(
                name=args.name,
                type="service_center",
                owner_id=owner.id,
            )
            db.add(center)
            action = "created"

        center.name = args.name

        if args.address is not None:
            center.address = args.address

        if args.phone is not None:
            center.phone = args.phone

        if args.latitude is not None:
            center.latitude = args.latitude
            center.longitude = args.longitude

        if opening_hours is not None:
            center.opening_hours = opening_hours

        if args.category_ids is not None:
            center.categories = load_items(db, Category, args.category_ids, "category IDs")

        if args.service_ids is not None:
            center.services = load_items(db, Service, args.service_ids, "service IDs")

        db.commit()
        db.refresh(center)

        print(f"Service center {action} successfully.")
        print(f"Public ID: {center.public_id}")
        print(f"Name: {center.name}")
        print(f"Owner: {owner.email}")


def main() -> None:
    args = parse_args()

    try:
        run(args)
    except ValueError as exc:
        raise SystemExit(f"Error: {exc}") from exc


if __name__ == "__main__":
    main()
