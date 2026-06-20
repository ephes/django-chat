from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from django_chat.imports.feed_smoke import format_feed_smoke_result
from django_chat.imports.live_feed_parity import (
    DEFAULT_FETCH_TIMEOUT,
    compare_django_chat_live_feed,
)
from django_chat.imports.source_data import RSS_FEED_URL


class Command(BaseCommand):
    help = (
        "Compare the live Simplecast podcast feed against a candidate self-hosted Django Chat "
        "podcast feed URL (django-cast route, staging, or the exact S3/CDN-served XML) and fail "
        "on any subscriber-affecting regression. Both feeds are fetched through the SSRF guard."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--candidate-url",
            required=True,
            help=(
                "Candidate self-hosted podcast feed URL to validate, e.g. the generated "
                "django-cast podcast RSS route or the published S3/CDN feed object."
            ),
        )
        parser.add_argument(
            "--source-url",
            default=RSS_FEED_URL,
            help=f"Live source RSS feed URL to compare against. Defaults to {RSS_FEED_URL}.",
        )
        parser.add_argument(
            "--timeout",
            type=float,
            default=DEFAULT_FETCH_TIMEOUT,
            help=f"Per-request fetch timeout in seconds. Defaults to {DEFAULT_FETCH_TIMEOUT}.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        result = compare_django_chat_live_feed(
            source_url=options["source_url"],
            candidate_url=options["candidate_url"],
            timeout=options["timeout"],
        )
        self.stdout.write(format_feed_smoke_result(result))
        if not result.passed:
            raise CommandError("Django Chat live feed parity check failed.")
