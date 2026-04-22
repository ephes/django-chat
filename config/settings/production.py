"""Production deployment settings for Django Chat."""

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

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
        "LOCATION": env("DJANGO_CACHE_LOCATION", default=str(ROOT_DIR / "cache")),
    },
}
