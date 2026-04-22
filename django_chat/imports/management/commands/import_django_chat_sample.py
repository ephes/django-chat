from __future__ import annotations

from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandParser

from django_chat.imports.import_sample import DEFAULT_SOURCE_FIXTURE_DIR, import_django_chat_sample


class Command(BaseCommand):
    help = (
        "Import the small fixture-backed Django Chat podcast/episode sample. "
        "This command reads committed local fixtures and downloads media only with --copy-audio."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--fixture-dir",
            type=Path,
            default=DEFAULT_SOURCE_FIXTURE_DIR,
            help=(
                "Directory containing slice 3 Django Chat source fixtures. "
                f"Defaults to {DEFAULT_SOURCE_FIXTURE_DIR}."
            ),
        )
        parser.add_argument(
            "--copy-audio",
            action="store_true",
            help=(
                "Download and copy audio for the fixture-backed sample into configured media "
                "storage, then attach cast.Audio rows to the imported episodes."
            ),
        )

    def handle(self, *args: Any, **options: Any) -> None:
        result = import_django_chat_sample(
            options["fixture_dir"],
            copy_audio=options["copy_audio"],
        )

        self.stdout.write(
            self.style.SUCCESS(
                "Imported Django Chat sample: "
                f"podcast_created={result.podcast_created}, "
                f"episodes_created={result.episodes_created}, "
                f"episodes_total={len(result.episodes)}, "
                f"audio_created={result.audio_created}, "
                f"audio_copied={result.audio_copied}."
            )
        )
