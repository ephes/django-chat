from __future__ import annotations

from typing import Any

from cast.models import Audio
from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import transaction


class Command(BaseCommand):
    help = (
        "Bind cached audio file sizes to their current file names, as django-cast 0.2.68 "
        "and later require before trusting a cached size. Sizes are read from storage. "
        "Defaults to dry-run; pass --write to update the audio data."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Count the audio files whose cached size is not bound yet. This is the default.",
        )
        parser.add_argument(
            "--write",
            action="store_true",
            help="Read each unbound file size from storage and store it with the file name.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        if options["dry_run"] and options["write"]:
            msg = "--dry-run and --write are mutually exclusive."
            raise CommandError(msg)
        write = bool(options["write"])

        audios = bound = unbound = updated = changed_meanwhile = 0
        failures: list[str] = []
        for audio_pk in Audio.objects.order_by("pk").values_list("pk", flat=True):
            audios += 1
            audio = Audio.objects.get(pk=audio_pk)
            for audio_format in audio.audio_formats:
                file_field = getattr(audio, audio_format)
                if not file_field:
                    continue
                data = audio.data or {}
                if (
                    data.get("size", {}).get(audio_format) is not None
                    and data.get("size_file_names", {}).get(audio_format) == file_field.name
                ):
                    bound += 1
                    continue
                unbound += 1
                if not write:
                    continue
                file_name = file_field.name
                try:
                    size = file_field.size
                except Exception as exc:  # noqa: BLE001 - report every storage failure, continue
                    failures.append(
                        f"audio {audio_pk} {audio_format} {file_name}: {type(exc).__name__}"
                    )
                    continue
                if _store_size(audio_pk, audio_format, file_name, size):
                    updated += 1
                else:
                    changed_meanwhile += 1

        prefix = "Cached audio sizes" if write else "Dry-run audio size cache"
        self.stdout.write(
            f"{prefix}: audios={audios}, bound={bound}, unbound={unbound}, "
            f"updated={updated}, changed_meanwhile={changed_meanwhile}, failed={len(failures)}."
        )
        for failure in failures:
            self.stdout.write(f"Failed: {failure}")
        if failures:
            msg = f"{len(failures)} audio file size(s) could not be read from storage."
            raise CommandError(msg)


def _store_size(audio_pk: int, audio_format: str, file_name: str, size: int) -> bool:
    """Store one size under a row lock unless the file changed since it was read."""
    with transaction.atomic():
        audio = Audio.objects.select_for_update().get(pk=audio_pk)
        if getattr(audio, audio_format).name != file_name:
            return False
        data = dict(audio.data or {})
        sizes = dict(data.get("size") or {})
        names = dict(data.get("size_file_names") or {})
        sizes[audio_format] = size
        names[audio_format] = file_name
        data["size"] = sizes
        data["size_file_names"] = names
        Audio.objects.filter(pk=audio_pk).update(data=data)
    return True
