"""Local development settings for Django Chat."""

from .base import *  # noqa: F403
from .base import env

DEBUG = env.bool("DJANGO_DEBUG", default=True)

# The player transcript endpoint sends a 1-hour browser cache (good in
# production). In dev that masks freshly seeded/edited transcript data, so
# disable it locally — seeded speaker changes then show on the next page load
# (after one hard refresh to drop any already-cached entry).
MIDDLEWARE = [*MIDDLEWARE, "django_chat.core.middleware.DisableTranscriptCacheMiddleware"]  # noqa: F405
SECRET_KEY = env(
    "DJANGO_SECRET_KEY",
    default="django-chat-local-development-secret-key",
)
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "0.0.0.0"]

DATABASES["default"]["ATOMIC_REQUESTS"] = False  # noqa: F405

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

STORAGES["staticfiles"] = {  # noqa: F405
    "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "django-chat-local",
    },
}
