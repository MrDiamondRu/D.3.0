import re

from django.core.exceptions import ValidationError
from django.core.validators import URLValidator


PHONE_RE = re.compile(r"^\d{11}$")


def validate_phone_11_digits(value: str) -> None:
    if value and not PHONE_RE.match(value):
        raise ValidationError("Телефон должен содержать ровно 11 цифр.")


def validate_url_list(value) -> None:
    if value in (None, ""):
        return
    if not isinstance(value, list):
        raise ValidationError("Поле сайтов должно быть списком URL.")

    url_validator = URLValidator()
    for item in value:
        if not isinstance(item, str):
            raise ValidationError("Каждый элемент в списке сайтов должен быть строкой.")
        url_validator(item)
