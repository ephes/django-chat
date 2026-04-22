"""Base settings for the Django Chat project."""

import os
from pathlib import Path
from types import ModuleType
from typing import Any

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


def _env_first(*names: str, default: str | None = None) -> str | None:
    for name in names:
        value = os.environ.get(name)
        if value:
            return env(name)
    return default


def _env_required(*names: str) -> str:
    value = _env_first(*names)
    if value is not None:
        return value
    return env(names[0])


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
    "django_chat.imports.apps.ImportsConfig",
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
                "django_chat.core.context_processors.django_chat_source_metadata",
            ],
        },
    },
]

STATIC_URL = "/static/"
STATIC_ROOT = ROOT_DIR / "staticfiles"
STATICFILES_DIRS = [APPS_DIR / "static"]
STORAGES: dict[str, dict[str, Any]] = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

MEDIA_URL = "/media/"
MEDIA_ROOT = ROOT_DIR / "media"
MEDIA_STORAGE_BACKEND = env(
    "DJANGO_CHAT_MEDIA_STORAGE_BACKEND",
    default="filesystem",
)
if MEDIA_STORAGE_BACKEND == "s3":
    DJANGO_CHAT_S3_BUCKET_NAME = _env_required(
        "DJANGO_CHAT_S3_STORAGE_BUCKET_NAME",
        "DJANGO_AWS_STORAGE_BUCKET_NAME",
    )
    DJANGO_CHAT_S3_CUSTOM_DOMAIN = _env_first(
        "DJANGO_CHAT_S3_CUSTOM_DOMAIN",
        "CLOUDFRONT_DOMAIN",
        default="",
    )
    DJANGO_CHAT_S3_MEDIA_DOMAIN = (
        DJANGO_CHAT_S3_CUSTOM_DOMAIN
        if DJANGO_CHAT_S3_CUSTOM_DOMAIN
        else f"{DJANGO_CHAT_S3_BUCKET_NAME}.s3.amazonaws.com"
    )
    STORAGES["default"] = {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "access_key": _env_required(
                "DJANGO_CHAT_S3_ACCESS_KEY_ID",
                "DJANGO_AWS_ACCESS_KEY_ID",
            ),
            "secret_key": _env_required(
                "DJANGO_CHAT_S3_SECRET_ACCESS_KEY",
                "DJANGO_AWS_SECRET_ACCESS_KEY",
            ),
            "bucket_name": DJANGO_CHAT_S3_BUCKET_NAME,
            "endpoint_url": _env_first("DJANGO_CHAT_S3_ENDPOINT_URL"),
            "region_name": _env_first("DJANGO_CHAT_S3_REGION_NAME"),
            "custom_domain": DJANGO_CHAT_S3_CUSTOM_DOMAIN or None,
            "addressing_style": _env_first("DJANGO_CHAT_S3_ADDRESSING_STYLE"),
            "signature_version": env("DJANGO_CHAT_S3_SIGNATURE_VERSION", default="s3v4"),
            "querystring_auth": env.bool(
                "DJANGO_CHAT_S3_QUERYSTRING_AUTH",
                default=False,
            ),
            "file_overwrite": env.bool("DJANGO_CHAT_S3_FILE_OVERWRITE", default=False),
            "default_acl": env("DJANGO_CHAT_S3_DEFAULT_ACL", default=None),
            "object_parameters": {
                "CacheControl": env(
                    "DJANGO_CHAT_S3_CACHE_CONTROL",
                    default="max-age=604800, s-maxage=604800, must-revalidate",
                ),
            },
        },
    }
    MEDIA_URL = env(
        "DJANGO_CHAT_MEDIA_URL",
        default=f"https://{DJANGO_CHAT_S3_MEDIA_DOMAIN}/",
    )
elif MEDIA_STORAGE_BACKEND != "filesystem":
    msg = (
        "DJANGO_CHAT_MEDIA_STORAGE_BACKEND must be either 'filesystem' or 's3', "
        f"not {MEDIA_STORAGE_BACKEND!r}."
    )
    raise ValueError(msg)

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
    ("django_chat", "Django Chat"),
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
