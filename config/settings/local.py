"""Local development settings for Django Chat."""

from .base import *  # noqa: F403
from .base import env

DEBUG = True
SECRET_KEY = env(
    "DJANGO_SECRET_KEY",
    default="django-chat-local-development-secret-key",
)
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "0.0.0.0"]

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "django-chat-local",
    }
}
