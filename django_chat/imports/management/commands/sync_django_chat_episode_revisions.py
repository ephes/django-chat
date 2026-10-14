from __future__ import annotations

from typing import Any

from cast.models import Episode
from django.core.management.base import BaseCommand, CommandError, CommandParser

from django_chat.imports.models import EpisodeSourceMetadata
from django_chat.imports.revision_sync import (
    RevisionSyncResult,
    format_divergent_draft,
    sync_episode_revisions,
)


class Command(BaseCommand):
    help = (
        "Align each episode's latest Wagtail revision with repairs applied to the live row, "
        "so republishing does not revert them. Pending drafts get the idempotent show-note "
        "repairs in place, are never published, and are listed. Defaults to dry-run; pass "
        "--write to update revisions."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report planned revision updates without writing. This is the default.",
        )
        parser.add_argument(
            "--write",
            action="store_true",
            help="Update latest revisions. Safe to re-run; in-sync revisions are skipped.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        if options["dry_run"] and options["write"]:
            msg = "--dry-run and --write are mutually exclusive."
            raise CommandError(msg)

        write = bool(options["write"])
        result = sync_episode_revisions(
            Episode=Episode,
            EpisodeSourceMetadata=EpisodeSourceMetadata,
            write=write,
        )
        for line in format_revision_sync_report(result, write=write):
            self.stdout.write(line)


def format_revision_sync_report(result: RevisionSyncResult, *, write: bool) -> list[str]:
    prefix = "Synced episode revisions" if write else "Dry-run episode revision sync"
    lines = [
        f"{prefix}: "
        f"episodes_scanned={result.episodes_scanned}, "
        f"without_revision={result.without_revision}, "
        f"already_in_sync={result.already_in_sync}, "
        f"revisions_synced={result.revisions_synced}, "
        f"drafts_repaired={result.drafts_repaired}, "
        f"divergent_drafts={len(result.divergent_drafts)}."
    ]
    if result.divergent_drafts:
        lines.append("Unpublished drafts (not published; review in Wagtail):")
        lines.extend(f"  {format_divergent_draft(draft)}" for draft in result.divergent_drafts)
    return lines
