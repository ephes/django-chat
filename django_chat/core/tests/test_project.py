import os
import subprocess
import sys
from pathlib import Path

import pytest
from django.conf import settings
from django.test import Client
from django.urls import resolve, reverse


def test_project_uses_django_chat_settings() -> None:
    assert settings.WAGTAIL_SITE_NAME == "Django Chat"
    assert settings.ROOT_URLCONF == "config.urls"
    assert settings.DJANGO_CHAT_WAGTAIL_ADMIN_PATH == "cms/"
    assert settings.WAGTAILADMIN_BASE_URL == "http://localhost:8000/cms/"
    assert "django.contrib.postgres" in settings.INSTALLED_APPS
    assert settings.STORAGES["staticfiles"] == {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    }
    assert settings.DATABASES["default"]["ATOMIC_REQUESTS"] is False


def test_wagtail_admin_url_is_mounted() -> None:
    assert reverse("wagtailadmin_home") == "/cms/"
    match = resolve("/cms/")
    assert match.url_name == "wagtailadmin_home"


def test_cast_urls_are_mounted() -> None:
    assert reverse("cast:styleguide") == "/styleguide/"


@pytest.mark.django_db
def test_cast_404_handler_renders_without_static_manifest(client: Client) -> None:
    response = client.get("/does-not-exist/")

    assert response.status_code == 404


def test_cast_app_ordering_is_pinned() -> None:
    installed_apps = list(settings.INSTALLED_APPS)

    assert installed_apps.index("crispy_bootstrap5") < installed_apps.index(
        "cast_bootstrap5.apps.CastBootstrap5Config",
    )
    assert installed_apps.index("cast_bootstrap5.apps.CastBootstrap5Config") < installed_apps.index(
        "cast.apps.CastConfig",
    )


def test_transcript_task_backends_are_immediate_for_tests() -> None:
    assert set(settings.TASKS) == {"default", "cast_transcripts"}
    assert settings.TASKS["default"] == {
        "BACKEND": "django_tasks.backends.immediate.ImmediateBackend",
    }
    assert settings.TASKS["cast_transcripts"] == {
        "BACKEND": "django_tasks.backends.immediate.ImmediateBackend",
    }


def test_tests_do_not_read_local_dotenv_file() -> None:
    assert settings.READ_DOT_ENV_FILE is False
    assert settings.SECRET_KEY == "django-chat-test-secret-key"


def test_test_settings_ignore_local_dotenv_secret(tmp_path: Path) -> None:
    settings_dir = tmp_path / "config" / "settings"
    settings_dir.mkdir(parents=True)
    base_settings = Path(settings.ROOT_DIR) / "config" / "settings" / "base.py"
    probe_settings = settings_dir / "base.py"
    probe_settings.write_text(
        base_settings.read_text()
        + "\nprint(os.environ.get('DJANGO_SECRET_KEY', 'missing'))\n"
        + "print(READ_DOT_ENV_FILE)\n",
    )
    (tmp_path / ".env").write_text(
        "DJANGO_SECRET_KEY=sentinel-from-dotenv\n"
        "DJANGO_READ_DOT_ENV_FILE=True\n"
        "DJANGO_DEBUG=True\n",
    )
    env = os.environ.copy()
    env.pop("DJANGO_SECRET_KEY", None)
    env["DJANGO_SETTINGS_MODULE"] = "config.settings.test"

    result = subprocess.run(
        [sys.executable, str(probe_settings)],
        check=True,
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.stdout.splitlines() == ["missing", "False"]
