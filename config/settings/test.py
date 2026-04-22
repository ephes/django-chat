"""Test settings for Django Chat."""

from .base import *  # noqa: F403

DEBUG = False
SECRET_KEY = "django-chat-test-secret-key"
ALLOWED_HOSTS = ["testserver", "localhost", "127.0.0.1"]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
        "ATOMIC_REQUESTS": False,
    },
}

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

STORAGES["default"] = {  # noqa: F405
    "BACKEND": "django.core.files.storage.FileSystemStorage",
}
STORAGES["staticfiles"] = {  # noqa: F405
    "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
}
MEDIA_URL = "/media/"
MEDIA_ROOT = ROOT_DIR / "test-media"  # noqa: F405
WHITENOISE_AUTOREFRESH = True

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "django-chat-test",
    },
}

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
