"""Base settings for the Django Chat project."""

import os
from pathlib import Path
from types import ModuleType
from typing import Any

import cast
import environ
from cast.apps import CAST_APPS, CAST_MIDDLEWARE

ROOT_DIR = Path(__file__).resolve(strict=True).parents[2]
APPS_DIR = ROOT_DIR / "django_chat"
# django-cast ≤ 0.2.55 listed `django_tasks.backends.database` in CAST_APPS;
# 0.2.56 changed it to plain `django_tasks`. Our TASKS config below routes
# `cast_transcripts` through `django_tasks_db.DatabaseBackend`, so we must
# ensure `django_tasks_db` ends up in INSTALLED_APPS regardless of which
# cast version is installed:
#   - replace any legacy `django_tasks.backends.database` entry (not
#     importable) with `django_tasks_db`,
#   - then append `django_tasks_db` if it isn't there yet,
#   - de-dupe in case both old and new shapes coexist.
CAST_APPS_COMPAT = [
    "django_tasks_db" if app == "django_tasks.backends.database" else app for app in CAST_APPS
]
if "django_tasks_db" not in CAST_APPS_COMPAT:
    CAST_APPS_COMPAT.append("django_tasks_db")
_seen: set[str] = set()
CAST_APPS_COMPAT = [app for app in CAST_APPS_COMPAT if not (app in _seen or _seen.add(app))]

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
    "django.contrib.postgres",
    "django.contrib.sessions",
    "django.contrib.sites",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = list(CAST_APPS_COMPAT)

LOCAL_APPS = [
    "django_chat.core.apps.CoreConfig",
    "django_chat.imports.apps.ImportsConfig",
    "django_chat.sponsor.apps.SponsorConfig",
    "django_chat.show_notes.apps.ShowNotesConfig",
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
    },
    "cast_transcripts": {
        "BACKEND": "django_tasks_db.DatabaseBackend",
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
        "BACKEND": "django_chat.core.staticfiles.MinifiedCompressedManifestStaticFilesStorage",
    },
}
DJANGO_CHAT_MINIFY_STATIC_CSS = env.bool("DJANGO_CHAT_MINIFY_STATIC_CSS", default=True)
DJANGO_CHAT_MINIFY_STATIC_CSS_PATTERNS = ("django_chat/css/*.css",)

MEDIA_URL = "/media/"
MEDIA_ROOT = ROOT_DIR / "media"
MEDIA_STORAGE_BACKEND = env(
    "DJANGO_CHAT_MEDIA_STORAGE_BACKEND",
    default="filesystem",
)

CAST_POST_BODY_BLOCKS = {
    "detail": [
        "django_chat.show_notes.blocks.sponsor_block",
        "django_chat.show_notes.blocks.link_list_block",
        "django_chat.show_notes.blocks.heading_block",
    ],
}

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

DJANGO_CHAT_PODCAST_SLUG = "episodes"

CRISPY_ALLOWED_TEMPLATE_PACKS = ["bootstrap4"]
CRISPY_TEMPLATE_PACK = "bootstrap4"

# Activate django-cast's comment app as the django-contrib-comments backend
# (threaded CastComment model, CastCommentForm, honeypot, and the
# cast.moderation.Moderator + SpamFilter). cast.comments is already installed;
# without this routing, django_comments would fall back to its own plain model
# and form.
COMMENTS_APP = "cast.comments"
CAST_COMMENTS_ENABLED = env.bool("CAST_COMMENTS_ENABLED", default=False)
# Identity is anonymous name/email only (see the comments-activation spec): drop
# the optional URL and title fields from the comment form so they never render.
CAST_COMMENTS_EXCLUDE_FIELDS = ("url", "title")
# Let comment authors edit and delete their own still-public, unanswered comments
# from the same browser session (django-cast's session-bound ownership model).
# Default off per environment; local.py turns it on for development. Requires a
# server-side session backend — the project default (DB-backed sessions) is fine;
# cast.E006 rejects the signed_cookies backend when this is on.
CAST_COMMENTS_ALLOW_AUTHOR_EDITS = env.bool("CAST_COMMENTS_ALLOW_AUTHOR_EDITS", default=False)
# Episode-page audio player: django-cast's custom player, in all environments.
# The Podlove Web Player path was removed after the staging cutover; restoring
# it would mean reverting the removal commit, not flipping this setting.
CAST_AUDIO_PLAYER = "custom"
# Registered themes in the Wagtail TemplateBaseDirectory choice list.
# `django_chat` is the project theme (see ensure_default_site for how this
# gets pinned per-site at deploy time).
CAST_CUSTOM_THEMES = [
    ("django_chat", "Django Chat"),
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
}

CAST_FILTERSET_FACETS = ["search", "date", "date_facets", "o"]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
