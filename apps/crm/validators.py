import re
from urllib.parse import urlsplit, urlunsplit

from django.core.exceptions import ValidationError
from django.core.validators import URLValidator


PHONE_RE = re.compile(r"^\d{11}$")


def normalize_url_idna(url: str) -> str:
    """Приводит URL к виду с punycode-хостом для HTTP-клиентов."""
    url = (url or "").strip()
    if not url:
        return url
    if "://" not in url:
        url = f"https://{url}"
    parts = urlsplit(url)
    hostname = parts.hostname
    if not hostname:
        return url
    try:
        ascii_host = hostname.encode("idna").decode("ascii")
    except UnicodeError:
        ascii_host = hostname
    userinfo = ""
    if parts.username is not None:
        userinfo = parts.username
        if parts.password is not None:
            userinfo += f":{parts.password}"
        userinfo += "@"
    netloc = f"{userinfo}{ascii_host}"
    if parts.port is not None:
        netloc += f":{parts.port}"
    return urlunsplit((parts.scheme, netloc, parts.path or "", parts.query, parts.fragment))


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
        url_validator(normalize_url_idna(item))
