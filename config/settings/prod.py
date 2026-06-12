from .base import *  # noqa: F401,F403


DEBUG = False
ALLOWED_HOSTS = [x.strip() for x in env("DJANGO_ALLOWED_HOSTS", "").split(",") if x.strip()]
if "10.10.10.135" not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append("10.10.10.135")

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("POSTGRES_DB", ""),
        "USER": env("POSTGRES_USER", ""),
        "PASSWORD": env("POSTGRES_PASSWORD", ""),
        "HOST": env("POSTGRES_HOST", "127.0.0.1"),
        "PORT": env("POSTGRES_PORT", "5432"),
    }
}

CSRF_TRUSTED_ORIGINS = [x.strip() for x in env("CSRF_TRUSTED_ORIGINS", "").split(",") if x.strip()]
