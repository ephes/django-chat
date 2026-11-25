"""Authentication boundaries outside the login forms: session-only API, password validators."""

from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.test import Client
from django.urls import reverse

ROOT_DIR = Path(__file__).resolve().parents[3]


def basic_auth(username: str, password: str) -> str:
    token = base64.b64encode(f"{username}:{password}".encode()).decode()
    return f"Basic {token}"


@pytest.mark.django_db
def test_api_does_not_accept_http_basic_credentials() -> None:
    # DRF's default BasicAuthentication would check a password on every API
    # request, outside the login forms and without CSRF.
    get_user_model().objects.create_superuser(
        username="synthetic-admin", email="admin@example.invalid", password="password"
    )
    url = reverse("cast:api:audio_list")

    right = Client().get(url, HTTP_AUTHORIZATION=basic_auth("synthetic-admin", "password"))
    wrong = Client().get(url, HTTP_AUTHORIZATION=basic_auth("synthetic-admin", "wrong"))

    assert right.status_code == 403
    assert wrong.status_code == 403
    assert right.content == wrong.content
    assert "WWW-Authenticate" not in right


@pytest.mark.django_db
def test_api_still_accepts_the_admin_session() -> None:
    user = get_user_model().objects.create_superuser(
        username="synthetic-admin", email="admin@example.invalid", password="password"
    )
    client = Client()
    client.force_login(user)

    assert client.get(reverse("cast:api:audio_list")).status_code == 200


@pytest.mark.parametrize("password", ["password", "12345678", "synthetic-admin", "short"])
def test_weak_passwords_are_refused(password: str) -> None:
    user = get_user_model()(username="synthetic-admin", email="admin@example.invalid")

    with pytest.raises(ValidationError):
        validate_password(password, user)


def test_a_long_generated_password_is_accepted() -> None:
    user = get_user_model()(username="synthetic-admin", email="admin@example.invalid")

    validate_password("correct-horse-battery-staple-7319", user)


def test_production_settings_keep_the_api_session_only(tmp_path: Path) -> None:
    env = {
        "PATH": os.environ["PATH"],
        "DJANGO_READ_DOT_ENV_FILE": "False",
        "DJANGO_" + "SECRET_KEY": "test-value",
        "DJANGO_ALLOWED_HOSTS": "django-chat.example.invalid,localhost",
        "DJANGO_SETTINGS_MODULE": "config.settings.production",
        "DJANGO_CHAT_MEDIA_STORAGE_BACKEND": "filesystem",
        "DATABASE_URL": "sqlite:///:memory:",
        "DJANGO_CACHE_LOCATION": str(tmp_path / "cache"),
    }
    script = (
        "import json; from django.conf import settings; "
        "print(json.dumps({"
        "'caches': sorted(settings.CACHES), "
        "'default_cache': settings.CACHES['default']['LOCATION'], "
        "'auth': list(settings.REST_FRAMEWORK['DEFAULT_AUTHENTICATION_CLASSES']), "
        "'num_proxies': settings.REST_FRAMEWORK.get('NUM_PROXIES')}))"
    )

    result = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        cwd=ROOT_DIR,
        env=env,
        capture_output=True,
        text=True,
    )
    values = json.loads(result.stdout)

    assert values["caches"] == ["default"]
    assert values["default_cache"] == str(tmp_path / "cache")
    assert values["auth"] == ["rest_framework.authentication.SessionAuthentication"]
    # Traefik replaces X-Forwarded-For; see docs/local-development.md.
    assert values["num_proxies"] is None
