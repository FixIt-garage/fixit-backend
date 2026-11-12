import re
from typing import Annotated

from pydantic import AfterValidator, HttpUrl, StringConstraints, TypeAdapter

PHONE_RE = re.compile(r"^\+380[0-9]{9}$")


def normalize_phone(value: str) -> str:
    """Drop spaces, dashes and brackets, then require the +380XXXXXXXXX format."""
    cleaned = re.sub(r"[\s\-()]", "", value)
    if not PHONE_RE.fullmatch(cleaned):
        raise ValueError("Phone must be in the format +380XXXXXXXXX")
    return cleaned


Phone = Annotated[str, AfterValidator(normalize_phone)]
Address = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]


AVATAR_URL_MAX_LENGTH = 500
_http_url = TypeAdapter(HttpUrl)


def validate_avatar_url(value: str) -> str:
    """Require a real http(s) URL with a host and return it as a plain string."""
    try:
        url = str(_http_url.validate_python(value.strip()))
    except ValueError as exc:
        raise ValueError("Avatar must be a valid http or https URL") from exc
    if len(url) > AVATAR_URL_MAX_LENGTH:
        raise ValueError(f"Avatar URL must be at most {AVATAR_URL_MAX_LENGTH} characters")
    return url


AvatarUrl = Annotated[str, AfterValidator(validate_avatar_url)]
