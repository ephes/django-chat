from __future__ import annotations

from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError, CommandParser

from django_chat.imports.feed_smoke import (
    compare_django_chat_sample_feed,
    format_feed_smoke_result,
)
from django_chat.imports.import_sample import DEFAULT_SOURCE_FIXTURE_DIR


class Command(BaseCommand):
    help = (
        "Compare the generated django-cast podcast RSS feed for the imported Django Chat "
        "sample against the committed Simplecast RSS fixture."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--fixture-dir",
            type=Path,
            default=DEFAULT_SOURCE_FIXTURE_DIR,
            help=(
                "Directory containing Django Chat source fixtures. "
                f"Defaults to {DEFAULT_SOURCE_FIXTURE_DIR}."
            ),
        )
        parser.add_argument(
            "--podcast-slug",
            default=settings.DJANGO_CHAT_PODCAST_SLUG,
            help=(
                "Imported podcast slug to compare. "
                f"Defaults to {settings.DJANGO_CHAT_PODCAST_SLUG}."
            ),
        )
        parser.add_argument(
            "--audio-format",
            default="mp3",
            help="Podcast audio format route segment to compare. Defaults to mp3.",
        )
        parser.add_argument(
            "--host",
            default="localhost",
            help=(
                "HTTP host used by Django's local test client when rendering the feed. "
                "Defaults to localhost."
            ),
        )

    def handle(self, *args: Any, **options: Any) -> None:
        result = compare_django_chat_sample_feed(
            options["fixture_dir"],
            podcast_slug=options["podcast_slug"],
            audio_format=options["audio_format"],
            host=options["host"],
        )
        self.stdout.write(format_feed_smoke_result(result))
        if not result.passed:
            raise CommandError("Django Chat feed smoke check failed.")
