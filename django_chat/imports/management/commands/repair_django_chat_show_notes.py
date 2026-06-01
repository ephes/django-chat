from __future__ import annotations

from typing import Any

from cast.models import Episode
from django.core.management.base import BaseCommand, CommandError, CommandParser

from django_chat.imports.models import EpisodeSourceMetadata
from django_chat.imports.show_note_backfill import (
    EpisodeShowNoteRepair,
    ShowNoteRepairResult,
    repair_imported_episode_show_notes,
)


class Command(BaseCommand):
    help = (
        "Repair imported Django Chat show-note bodies and episode summary metadata. "
        "Defaults to dry-run; pass --write to update the database."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report planned repairs without writing. This is the default.",
        )
        parser.add_argument(
            "--write",
            action="store_true",
            help="Apply the repair. Safe to re-run; unchanged rows are skipped.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        if options["dry_run"] and options["write"]:
            msg = "--dry-run and --write are mutually exclusive."
            raise CommandError(msg)

        write = bool(options["write"])
        result = repair_imported_episode_show_notes(
            Episode=Episode,
            EpisodeSourceMetadata=EpisodeSourceMetadata,
            write=write,
            collect_items=options["verbosity"] >= 2,
        )
        self.stdout.write(_format_summary(result, write=write))

        if options["verbosity"] >= 2:
            for item in result.items:
                self.stdout.write(_format_item(item))


def _format_summary(result: ShowNoteRepairResult, *, write: bool) -> str:
    prefix = "Repaired" if write else "Dry-run show-note repair"
    return (
        f"{prefix}: "
        f"episodes_scanned={result.episodes_scanned}, "
        f"body_rows_changed={result.body_rows_changed}, "
        f"search_description_rows_changed={result.search_description_rows_changed}, "
        f"source_detail_blocks_restored={result.source_detail_blocks_restored}, "
        f"implicit_link_lists_converted={result.implicit_link_lists_converted}, "
        f"implicit_link_list_headings_hidden={result.implicit_link_list_headings_hidden}, "
        f"implicit_link_lists_skipped={result.implicit_link_lists_skipped}, "
        f"support_copy_sections_restored={result.support_copy_sections_restored}, "
        f"raw_markdown_like_episodes={result.raw_markdown_like_episodes}."
    )


def _format_item(item: EpisodeShowNoteRepair) -> str:
    actions = []
    if item.body_changed:
        actions.append("body")
    if item.search_description_changed:
        actions.append("search_description")
    if item.source_detail_blocks_restored:
        actions.append(f"source_detail_restored={item.source_detail_blocks_restored}")
    if item.implicit_link_lists_converted:
        actions.append(f"converted_lists={item.implicit_link_lists_converted}")
    if item.implicit_link_list_headings_hidden:
        actions.append(f"hidden_implicit_link_headings={item.implicit_link_list_headings_hidden}")
    if item.implicit_link_lists_skipped:
        actions.append(f"skipped_lists={item.implicit_link_lists_skipped}")
    if item.support_copy_sections_restored:
        actions.append(f"support_copy_restored={item.support_copy_sections_restored}")
    if item.raw_markdown_like:
        actions.append("raw_markdown_like")

    return f"{item.slug}: {', '.join(actions)} ({item.title})"
