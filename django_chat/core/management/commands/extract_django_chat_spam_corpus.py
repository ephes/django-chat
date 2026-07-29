from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from django_chat.core.spamfilter.corpus import CorpusError, extract_comment_corpus, label_counts


class Command(BaseCommand):
    help = (
        "Extract the labelled comment corpus from a python-podcast PostgreSQL dump "
        "for spam-filter training. Reads a dump rather than a live database so the "
        "pipeline never touches python-podcast production."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "dump",
            type=Path,
            help="Path to a python-podcast pg_dump (.sql or .sql.gz).",
        )
        parser.add_argument(
            "--output",
            type=Path,
            required=True,
            help="Where to write the labelled corpus as JSON.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        # call_command(...) bypasses argparse's type coercion, so normalise here.
        dump = Path(options["dump"])
        output = Path(options["output"])

        if not dump.exists():
            raise CommandError(f"Dump not found: {dump}")

        try:
            corpus = extract_comment_corpus(dump)
        except CorpusError as exc:
            raise CommandError(str(exc)) from exc

        counts = label_counts(corpus)
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("w", encoding="utf-8") as handle:
            json.dump(corpus, handle)

        self.stdout.write(
            f"Extracted {len(corpus)} comments "
            f"({counts.get('spam', 0)} spam, {counts.get('ham', 0)} ham) -> {output}"
        )
        if counts.get("ham", 0) < 50:
            self.stdout.write(
                self.style.WARNING(
                    "Ham class is very small; the corpus alone cannot teach the filter "
                    "English ham. Add transcript lines (see docs/spam-filter.md)."
                )
            )
