from __future__ import annotations

from io import StringIO

import pytest
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
def test_command_is_idempotent_when_values_match(monkeypatch) -> None:
    site = Site.objects.get(is_default_site=True)
    site.hostname = "djangochat.staging.django-cast.com"
    site.port = 443
    site.save()

    out = StringIO()
    call_command(
        "ensure_default_site",
        hostname="djangochat.staging.django-cast.com",
        port=443,
        stdout=out,
    )

    assert "no change" in out.getvalue()


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
