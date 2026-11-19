"""Production deployment settings for Django Chat."""

import os

from .base import *  # noqa: F403
from .base import ROOT_DIR, env

DEBUG = False
SECRET_KEY = env("DJANGO_SECRET_KEY")
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS")
_primary_allowed_host = ALLOWED_HOSTS[0] if ALLOWED_HOSTS else "localhost"

ADMIN_URL = env("DJANGO_ADMIN_URL", default=ADMIN_URL)  # noqa: F405
DJANGO_CHAT_WAGTAIL_ADMIN_PATH = env(  # noqa: F405
    "DJANGO_CHAT_WAGTAIL_ADMIN_PATH",
    default=DJANGO_CHAT_WAGTAIL_ADMIN_PATH,  # noqa: F405
)
WAGTAILADMIN_BASE_URL = env(  # noqa: F405
    "DJANGO_CHAT_WAGTAIL_ADMIN_BASE_URL",
    default=f"https://{_primary_allowed_host}/{DJANGO_CHAT_WAGTAIL_ADMIN_PATH}",
)

CSRF_TRUSTED_ORIGINS = env.list(
    "DJANGO_CSRF_TRUSTED_ORIGINS",
    default=[f"https://{host}" for host in ALLOWED_HOSTS if host not in {"localhost", "127.0.0.1"}],
)

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = env.bool("DJANGO_SECURE_SSL_REDIRECT", default=True)
SECURE_HSTS_SECONDS = env.int("DJANGO_SECURE_HSTS_SECONDS", default=60)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool(
    "DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS",
    default=False,
)
SECURE_HSTS_PRELOAD = env.bool("DJANGO_SECURE_HSTS_PRELOAD", default=False)
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

SERVER_EMAIL = env("DJANGO_SERVER_EMAIL", default="server@example.invalid")
DEFAULT_FROM_EMAIL = env("DJANGO_DEFAULT_FROM_EMAIL", default=SERVER_EMAIL)
EMAIL_SUBJECT_PREFIX = "[Django Chat] "

_CACHE_LOCATION = env("DJANGO_CACHE_LOCATION", default=str(ROOT_DIR / "cache"))
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
        "LOCATION": _CACHE_LOCATION,
    },
    # Failed admin login counters (docs/admin-login-throttle.md). A separate
    # directory, so clearing the default cache on a view restriction change
    # does not reset lockouts. The backend drops expired counters before it
    # culls, so only live entries count towards MAX_ENTRIES.
    "admin_login_throttle": {
        "BACKEND": "django_chat.core.cache_backends.ExpiringFileBasedCache",
        "LOCATION": os.path.join(_CACHE_LOCATION, "admin-login-throttle"),
        "OPTIONS": {"MAX_ENTRIES": 100000},
    },
}
# One lock shared by all Gunicorn workers on this host. FileBasedCache.clear()
# deletes only *.djcache files, so clearing a cache never replaces the lock.
ADMIN_LOGIN_THROTTLE_LOCK_PATH = os.path.join(_CACHE_LOCATION, "admin-login-throttle.lock")

# Transcript speaker labels are editorial content.  The django-cast player
# endpoint is cacheable by default, which is useful for stable public sites but
# can leave staging reviewers looking at an hour-old speaker correction.  Keep
# this opt-in so production can retain the upstream policy while staging always
# reflects the latest reviewed transcript.
if env.bool("DJANGO_CHAT_DISABLE_TRANSCRIPT_CACHE", default=False):
    MIDDLEWARE = [*MIDDLEWARE, "django_chat.core.middleware.DisableTranscriptCacheMiddleware"]  # noqa: F405
