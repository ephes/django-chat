from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from django_chat.core.spamfilter.transcripts import iter_transcript_lines


class Command(BaseCommand):
    help = (
        "Collect Django Chat transcript lines to use as English ham training data "
        "for the comment spam filter. Transcript.dote is a FileField, so this needs "
        "the app's transcript storage configured -- run it where the site runs."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--output",
            type=Path,
            required=True,
            help="Where to write the transcript lines as a JSON list.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        # call_command(...) bypasses argparse's type coercion, so normalise here.
        output = Path(options["output"])

        lines: list[str] = []
        transcript_ids: set[int] = set()
        for transcript_id, text in iter_transcript_lines():
            transcript_ids.add(transcript_id)
            lines.append(text)

        if not lines:
            raise CommandError(
                "No transcript lines found. Either no transcripts have a DOTe payload, "
                "or transcript storage is not reachable from here."
            )

        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("w", encoding="utf-8") as handle:
            json.dump(lines, handle)

        words = sum(len(text.split()) for text in lines)
        self.stdout.write(
            f"Collected {len(lines)} lines (~{words} words) "
            f"from {len(transcript_ids)} transcripts -> {output}"
        )
