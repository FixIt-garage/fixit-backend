from app.models.user import User, UserRole
from app.schemas.user import ProfileCompleteness


def _is_filled(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list | tuple | set):
        return len(value) > 0
    return True


def _client_fields(user: User) -> list[tuple[str, object]]:
    return [
        ("avatar_url", user.avatar_url),
        ("phone", user.phone),
        ("address", user.address),
        ("city", user.city),
    ]


def _master_fields(user: User) -> list[tuple[str, object]]:
    master = user.master_profile
    return [
        ("categories", master.categories if master else None),
        ("city", user.city),
        ("experience_years", master.experience_years if master else None),
        ("call_out_price", master.call_out_price if master else None),
        ("schedule", master.schedule if master else None),
    ]


def calculate_completeness(user: User) -> ProfileCompleteness:
    """Share of filled profile fields and the first missing one (all fields weigh the same)."""
    fields = _master_fields(user) if user.role == UserRole.MASTER else _client_fields(user)
    missing = [name for name, value in fields if not _is_filled(value)]
    percent = round(100 * (len(fields) - len(missing)) / len(fields))
    return ProfileCompleteness(percent=percent, next_field=missing[0] if missing else None)
