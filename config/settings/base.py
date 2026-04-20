"""Base settings for the Django Chat project."""

import os
from pathlib import Path
from types import ModuleType

import cast
import cast_bootstrap5
import environ
from cast.apps import CAST_APPS, CAST_MIDDLEWARE

ROOT_DIR = Path(__file__).resolve(strict=True).parents[2]
APPS_DIR = ROOT_DIR / "django_chat"

env = environ.Env()

READ_DOT_ENV_FILE = env.bool("DJANGO_READ_DOT_ENV_FILE", default=True)
if os.environ.get("DJANGO_SETTINGS_MODULE") == "config.settings.test":
    READ_DOT_ENV_FILE = False

if READ_DOT_ENV_FILE:
    env.read_env(str(ROOT_DIR / ".env"))

DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.sites",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    *CAST_APPS[:-1],
    "crispy_bootstrap5",
    "cast_bootstrap5.apps.CastBootstrap5Config",
    CAST_APPS[-1],
]

LOCAL_APPS = [
    "django_chat.core.apps.CoreConfig",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    *CAST_MIDDLEWARE,
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DEBUG = env.bool("DJANGO_DEBUG", default=False)

DATABASES = {
    "default": env.db(
        "DATABASE_URL",
        default=f"sqlite:///{ROOT_DIR / 'db.sqlite3'}",
    ),
}
DATABASES["default"]["ATOMIC_REQUESTS"] = True

TASKS = {
    "default": {
        "BACKEND": "django_tasks.backends.immediate.ImmediateBackend",
        "ENQUEUE_ON_COMMIT": False,
    },
    "cast_transcripts": {
        "BACKEND": "django_tasks.backends.immediate.ImmediateBackend",
        "ENQUEUE_ON_COMMIT": False,
    },
}

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
SITE_ID = 1

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [APPS_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.template.context_processors.i18n",
                "django.template.context_processors.media",
                "django.template.context_processors.static",
                "django.template.context_processors.tz",
                "django.contrib.messages.context_processors.messages",
                "cast.context_processors.site_template_base_dir",
            ],
        },
    },
]

STATIC_URL = "/static/"
STATIC_ROOT = ROOT_DIR / "staticfiles"
STATICFILES_DIRS = [APPS_DIR / "static"]
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

MEDIA_URL = "/media/"
MEDIA_ROOT = ROOT_DIR / "media"

ADMIN_URL = "django-admin/"
DJANGO_CHAT_WAGTAIL_ADMIN_PATH = "cms/"
WAGTAILADMIN_BASE_URL = env(
    "DJANGO_CHAT_WAGTAIL_ADMIN_BASE_URL",
    default=f"http://localhost:8000/{DJANGO_CHAT_WAGTAIL_ADMIN_PATH}",
)
WAGTAIL_SITE_NAME = "Django Chat"
WAGTAILIMAGES_MAX_UPLOAD_SIZE = 30 * 1024 * 1024

CRISPY_ALLOWED_TEMPLATE_PACKS = ["bootstrap4", "bootstrap5"]
CRISPY_TEMPLATE_PACK = "bootstrap5"

CAST_COMMENTS_ENABLED = False
CAST_CUSTOM_THEMES = [
    ("bootstrap5", "Bootstrap 5"),
]


def _package_manifest_path(package: ModuleType, *path_parts: str) -> Path:
    package_file = package.__file__
    if package_file is None:
        msg = f"Package {package.__name__} does not expose a filesystem path."
        raise RuntimeError(msg)
    return (
        Path(package_file)
        .resolve()
        .parent.joinpath(
            "static",
            *path_parts,
            "manifest.json",
        )
    )


DJANGO_VITE = {
    "cast": {
        "static_url_prefix": "cast/vite/",
        "manifest_path": _package_manifest_path(cast, "cast", "vite"),
    },
    "cast-bootstrap5": {
        "static_url_prefix": "cast_bootstrap5/vite/",
        "manifest_path": _package_manifest_path(
            cast_bootstrap5,
            "cast_bootstrap5",
            "vite",
        ),
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
