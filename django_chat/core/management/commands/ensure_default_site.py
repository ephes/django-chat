"""Ensure the default Wagtail Site matches deploy-time configuration.

Reads ``DJANGO_CHAT_SITE_HOSTNAME``/``DJANGO_CHAT_SITE_PORT`` (with
``WAGTAIL_SITE_HOSTNAME``/``WAGTAIL_SITE_PORT`` as a fallback) and
updates the default ``wagtail.models.Site`` row when it differs. Also
ensures the site's ``TemplateBaseDirectory`` setting matches
``DJANGO_CHAT_SITE_TEMPLATE_BASE_DIR`` (default ``django_chat``) so the
django-cast theme lookup resolves to the project theme without each
request needing a query param. The theme assignment is what makes
``CAST_PODLOVE_PLAYER_THEMES`` actually take effect for player config
requests.

Saving the Site row triggers Wagtail's ``post_save`` signal, which
clears the cache of site root paths used to build canonical / OG URLs.

Idempotent: a no-op when the Site row and theme already match the
configured values.
"""

from __future__ import annotations

import os

from cast.models.theme import TemplateBaseDirectory
from django.core.management.base import BaseCommand, CommandError
from wagtail.models import Site

DEFAULT_TEMPLATE_BASE_DIR = "django_chat"


def _resolve(*names: str) -> str | None:
    for name in names:
        value = os.environ.get(name)
        if value:
            return value
    return None


class Command(BaseCommand):
    help = (
        "Update the default Wagtail Site to match DJANGO_CHAT_SITE_HOSTNAME / "
        "DJANGO_CHAT_SITE_PORT and ensure its TemplateBaseDirectory is set to "
        "DJANGO_CHAT_SITE_TEMPLATE_BASE_DIR (default django_chat)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--hostname",
            help="Hostname to set on the default Site. Falls back to env vars when omitted.",
        )
        parser.add_argument(
            "--port",
            type=int,
            help="Port to set on the default Site. Falls back to env vars when omitted.",
        )
        parser.add_argument(
            "--template-base-dir",
            help="Theme name for the site's TemplateBaseDirectory. Falls back to env vars.",
        )

    def handle(self, *args, **options):
        hostname = options.get("hostname") or _resolve(
            "DJANGO_CHAT_SITE_HOSTNAME", "WAGTAIL_SITE_HOSTNAME"
        )
        port_raw = options.get("port")
        if port_raw is None:
            port_str = _resolve("DJANGO_CHAT_SITE_PORT", "WAGTAIL_SITE_PORT")
            port_raw = int(port_str) if port_str else None

        if not hostname:
            raise CommandError("DJANGO_CHAT_SITE_HOSTNAME (or --hostname) is required.")
        port = port_raw if port_raw is not None else 443

        template_base_dir = (
            options.get("template_base_dir")
            or _resolve("DJANGO_CHAT_SITE_TEMPLATE_BASE_DIR")
            or DEFAULT_TEMPLATE_BASE_DIR
        )

        site = Site.objects.filter(is_default_site=True).first()
        if site is None:
            raise CommandError(
                "No default Wagtail Site exists. Create one before running this command."
            )

        any_change = False
        if site.hostname != hostname or site.port != port:
            previous = f"{site.hostname}:{site.port}"
            site.hostname = hostname
            site.port = port
            site.save()
            Site.clear_site_root_paths_cache()
            self.stdout.write(
                self.style.SUCCESS(
                    f"Updated default Site {previous} -> {hostname}:{port}; "
                    "cleared root-paths cache."
                )
            )
            any_change = True
        else:
            self.stdout.write(f"Default Site already matches {hostname}:{port}; no change.")

        theme_setting = TemplateBaseDirectory.for_site(site)
        if theme_setting.name != template_base_dir:
            previous_theme = theme_setting.name
            theme_setting.name = template_base_dir
            theme_setting.save()
            self.stdout.write(
                self.style.SUCCESS(
                    f"Updated TemplateBaseDirectory {previous_theme} -> {template_base_dir}."
                )
            )
            any_change = True
        else:
            self.stdout.write(
                f"TemplateBaseDirectory already set to {template_base_dir}; no change."
            )

        if not any_change:
            self.stdout.write("ensure_default_site: nothing to do.")
