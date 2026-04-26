from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from django_chat.imports.import_catalog import (
    build_import_plan,
    dry_run_catalog_import,
    import_django_chat_catalog,
    live_cover_image_downloader,
    load_live_catalog_source_data,
    timed_stream_audio_downloader,
)


class Command(BaseCommand):
    help = (
        "Import the live Django Chat RSS catalog, enriched with public Simplecast "
        "endpoint data when available. Audio and cover image copying are opt-in."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--copy-audio",
            action="store_true",
            help=(
                "Stream-copy episode audio into configured media storage. This can transfer "
                "about 11 GB for the full catalog; use deliberately."
            ),
        )
        parser.add_argument(
            "--copy-cover-image",
            action="store_true",
            help=(
                "Download the show artwork URL and attach it as the Podcast page's "
                "cover_image. Idempotent — skipped when cover_image is already set."
            ),
        )
        parser.add_argument(
            "--timeout",
            type=float,
            default=30.0,
            help="Per-request timeout in seconds for source and media fetches. Default: 30.",
        )
        parser.add_argument(
            "--max-episodes",
            type=int,
            default=None,
            help="Limit imported episodes for safe operator/test runs.",
        )
        parser.add_argument(
            "--simplecast-page-size",
            type=int,
            default=100,
            help="Initial Simplecast episode-list page size. Default: 100.",
        )
        parser.add_argument(
            "--simplecast-max-pages",
            type=int,
            default=None,
            help="Stop Simplecast pagination after this many pages.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Fetch source data and report the import plan, but roll back database writes.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        if options["copy_audio"] and options["dry_run"]:
            msg = "--copy-audio cannot be combined with --dry-run."
            raise CommandError(msg)
        if options["copy_cover_image"] and options["dry_run"]:
            msg = "--copy-cover-image cannot be combined with --dry-run."
            raise CommandError(msg)

        timeout = float(options["timeout"])
        catalog_source = load_live_catalog_source_data(
            timeout=timeout,
            max_episodes=options["max_episodes"],
            simplecast_page_size=int(options["simplecast_page_size"]),
            simplecast_max_pages=options["simplecast_max_pages"],
        )
        plan = build_import_plan(catalog_source.source_data)

        self.stdout.write(
            "Fetched Django Chat catalog source data: "
            f"rss_episodes={catalog_source.fetch_summary.rss_episode_count}, "
            "simplecast_list_episodes="
            f"{catalog_source.fetch_summary.simplecast_list_episode_count}, "
            "simplecast_detail_episodes="
            f"{catalog_source.fetch_summary.simplecast_detail_episode_count}, "
            f"simplecast_pages={catalog_source.fetch_summary.simplecast_page_count}, "
            f"source_links={catalog_source.fetch_summary.source_link_count}."
        )
        self.stdout.write(
            "Import plan: "
            f"merged_episodes={plan.merged_episode_count}, "
            f"source_audio_bytes={plan.source_audio_byte_size or 0}."
        )

        if options["dry_run"]:
            dry_run_plan = dry_run_catalog_import(catalog_source)
            self.stdout.write(
                self.style.SUCCESS(
                    "Dry-run catalog import rolled back: "
                    f"episodes_planned={dry_run_plan.merged_episode_count}, "
                    f"source_links={dry_run_plan.source_link_count}, "
                    f"source_audio_bytes={dry_run_plan.source_audio_byte_size or 0}."
                )
            )
            return

        result = import_django_chat_catalog(
            catalog_source,
            copy_audio=options["copy_audio"],
            audio_downloader=timed_stream_audio_downloader(timeout),
            cover_image_downloader=(
                live_cover_image_downloader(timeout) if options["copy_cover_image"] else None
            ),
        )
        imported = result.import_result
        self.stdout.write(
            self.style.SUCCESS(
                "Imported Django Chat catalog: "
                f"podcast_created={imported.podcast_created}, "
                f"episodes_created={imported.episodes_created}, "
                f"episodes_total={len(imported.episodes)}, "
                f"source_links={len(imported.source_links)}, "
                f"audio_created={imported.audio_created}, "
                f"audio_copied={imported.audio_copied}, "
                f"audio_skipped={imported.audio_skipped}."
            )
        )
