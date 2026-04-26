from __future__ import annotations

from io import StringIO

import pytest
from cast.models.theme import TemplateBaseDirectory
from django.core.management import call_command
from django.core.management.base import CommandError
from wagtail.models import Site


@pytest.mark.django_db
def test_command_updates_default_site_from_arguments() -> None:
    site = Site.objects.get(is_default_site=True)
    site.hostname = "localhost"
    site.port = 80
    site.save()

    out = StringIO()
    call_command(
        "ensure_default_site",
        hostname="djangochat.staging.django-cast.com",
        port=443,
        stdout=out,
    )

    site.refresh_from_db()
    assert site.hostname == "djangochat.staging.django-cast.com"
    assert site.port == 443
    assert "Updated default Site" in out.getvalue()


@pytest.mark.django_db
def test_command_is_idempotent_when_values_match() -> None:
    site = Site.objects.get(is_default_site=True)
    site.hostname = "djangochat.staging.django-cast.com"
    site.port = 443
    site.save()
    theme_setting = TemplateBaseDirectory.for_site(site)
    theme_setting.name = "django_chat"
    theme_setting.save()

    out = StringIO()
    call_command(
        "ensure_default_site",
        hostname="djangochat.staging.django-cast.com",
        port=443,
        stdout=out,
    )

    output = out.getvalue()
    assert "no change" in output
    assert "Updated default Site" not in output
    assert "Updated TemplateBaseDirectory" not in output


@pytest.mark.django_db
def test_command_falls_back_to_env_vars(monkeypatch) -> None:
    site = Site.objects.get(is_default_site=True)
    site.hostname = "localhost"
    site.port = 80
    site.save()

    monkeypatch.setenv("DJANGO_CHAT_SITE_HOSTNAME", "djangochat.example.com")
    monkeypatch.setenv("DJANGO_CHAT_SITE_PORT", "443")

    out = StringIO()
    call_command("ensure_default_site", stdout=out)

    site.refresh_from_db()
    assert site.hostname == "djangochat.example.com"
    assert site.port == 443


@pytest.mark.django_db
def test_command_raises_when_hostname_missing(monkeypatch) -> None:
    monkeypatch.delenv("DJANGO_CHAT_SITE_HOSTNAME", raising=False)
    monkeypatch.delenv("WAGTAIL_SITE_HOSTNAME", raising=False)

    with pytest.raises(CommandError, match="DJANGO_CHAT_SITE_HOSTNAME"):
        call_command("ensure_default_site")


@pytest.mark.django_db
def test_command_sets_template_base_dir_default() -> None:
    site = Site.objects.get(is_default_site=True)
    # Wagtail ships TemplateBaseDirectory default = bootstrap4. Confirm
    # the command flips it to django_chat without an explicit arg.
    theme_setting = TemplateBaseDirectory.for_site(site)
    theme_setting.name = "bootstrap4"
    theme_setting.save()

    out = StringIO()
    call_command(
        "ensure_default_site",
        hostname="djangochat.staging.django-cast.com",
        port=443,
        stdout=out,
    )

    theme_setting.refresh_from_db()
    assert theme_setting.name == "django_chat"
    assert "Updated TemplateBaseDirectory" in out.getvalue()


@pytest.mark.django_db
def test_command_template_base_dir_from_arg_or_env(monkeypatch) -> None:
    site = Site.objects.get(is_default_site=True)
    monkeypatch.setenv("DJANGO_CHAT_SITE_TEMPLATE_BASE_DIR", "django_chat")

    call_command(
        "ensure_default_site",
        hostname="djangochat.staging.django-cast.com",
        port=443,
        template_base_dir="vue",
    )

    theme_setting = TemplateBaseDirectory.for_site(site)
    # Explicit --template-base-dir wins over env var.
    assert theme_setting.name == "vue"
