from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand, CommandParser

from django_chat.imports.performance import (
    format_catalog_performance_result,
    measure_catalog_performance,
)


class Command(BaseCommand):
    help = (
        "Measure local generated feed timing/item count and episode-list timing/query count "
        "after importing Django Chat catalog data."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--podcast-slug",
            default="episodes",
            help="Imported podcast slug to measure. Defaults to episodes.",
        )
        parser.add_argument(
            "--audio-format",
            default="mp3",
            help="Podcast audio format route segment to measure. Defaults to mp3.",
        )
        parser.add_argument(
            "--host",
            default="localhost",
            help=(
                "HTTP host used by Django's local test client when rendering pages. "
                "Defaults to localhost."
            ),
        )

    def handle(self, *args: Any, **options: Any) -> None:
        result = measure_catalog_performance(
            podcast_slug=options["podcast_slug"],
            audio_format=options["audio_format"],
            host=options["host"],
        )
        self.stdout.write(format_catalog_performance_result(result))
