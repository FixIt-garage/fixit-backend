import re
from typing import Annotated

from pydantic import AfterValidator, StringConstraints

PHONE_RE = re.compile(r"^\+380\d{9}$")


def normalize_phone(value: str) -> str:
    """Drop spaces, dashes and brackets, then require the +380XXXXXXXXX format."""
    cleaned = re.sub(r"[\s\-()]", "", value)
    if not PHONE_RE.fullmatch(cleaned):
        raise ValueError("Phone must be in the format +380XXXXXXXXX")
    return cleaned


Phone = Annotated[str, AfterValidator(normalize_phone)]
Address = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
