from __future__ import annotations

from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandParser

from django_chat.imports.staging_transcripts import (
    DEFAULT_STAGING_HOST,
    import_staging_transcripts,
)


class Command(BaseCommand):
    help = "Import django-cast transcript artifacts from the Django Chat staging Podlove API."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--host",
            default=DEFAULT_STAGING_HOST,
            help=f"Staging host to read from. Defaults to {DEFAULT_STAGING_HOST}.",
        )
        parser.add_argument(
            "--podcast-slug",
            default=settings.DJANGO_CHAT_PODCAST_SLUG,
            help=(
                "Podcast route segment on staging. "
                f"Defaults to {settings.DJANGO_CHAT_PODCAST_SLUG}."
            ),
        )
        parser.add_argument(
            "--slug",
            action="append",
            default=None,
            help="Import only this episode slug. Can be passed multiple times.",
        )
        parser.add_argument(
            "--timeout",
            type=float,
            default=30.0,
            help="Per-request timeout in seconds. Default: 30.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        result = import_staging_transcripts(
            host=options["host"],
            podcast_slug=options["podcast_slug"],
            slugs=options["slug"],
            timeout=float(options["timeout"]),
        )
        for item in result.items:
            if item.imported:
                self.stdout.write(f"{item.slug}: imported {item.segment_count} segments")
            else:
                self.stdout.write(f"{item.slug}: skipped ({item.reason})")

        self.stdout.write(
            self.style.SUCCESS(
                "Imported staging transcripts: "
                f"imported={result.imported_count}, skipped={result.skipped_count}."
            )
        )
