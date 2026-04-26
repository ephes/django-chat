"""Ensure the default Wagtail Site matches deploy-time configuration.

Reads ``DJANGO_CHAT_SITE_HOSTNAME`` and ``DJANGO_CHAT_SITE_PORT`` (or the
matching ``WAGTAIL_SITE_HOSTNAME``/``WAGTAIL_SITE_PORT`` env vars) and
updates the default ``wagtail.models.Site`` row when it differs. Saving
the row triggers Wagtail's ``post_save`` signal, which clears the
file-based cache of site root paths used to build canonical / OG URLs.

Idempotent: a no-op when the Site row already matches the configured
hostname and port.
"""

from __future__ import annotations

import os

from django.core.management.base import BaseCommand, CommandError
from wagtail.models import Site


def _resolve(*names: str) -> str | None:
    for name in names:
        value = os.environ.get(name)
        if value:
            return value
    return None


class Command(BaseCommand):
    help = (
        "Update the default Wagtail Site to match DJANGO_CHAT_SITE_HOSTNAME "
        "and DJANGO_CHAT_SITE_PORT."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--hostname",
            help="Hostname to set on the default Site. Falls back to the env vars when omitted.",
        )
        parser.add_argument(
            "--port",
            type=int,
            help="Port to set on the default Site. Falls back to the env vars when omitted.",
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

        site = Site.objects.filter(is_default_site=True).first()
        if site is None:
            raise CommandError(
                "No default Wagtail Site exists. Create one before running this command."
            )

        if site.hostname == hostname and site.port == port:
            self.stdout.write(f"Default Site already matches {hostname}:{port}; no change.")
            return

        previous = f"{site.hostname}:{site.port}"
        site.hostname = hostname
        site.port = port
        site.save()
        Site.clear_site_root_paths_cache()
        self.stdout.write(
            self.style.SUCCESS(
                f"Updated default Site {previous} -> {hostname}:{port}; cleared root-paths cache."
            )
        )
