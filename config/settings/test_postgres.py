"""Disposable PostgreSQL integration tests; requires an explicit DATABASE_URL."""

from .base import env
from .test import *  # noqa: F403

DATABASES = {"default": env.db("DATABASE_URL")}
DATABASES["default"]["ATOMIC_REQUESTS"] = False
