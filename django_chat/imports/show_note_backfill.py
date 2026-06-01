from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from django.db import transaction
from django.utils.html import strip_tags

from django_chat.imports.show_notes import structure_episode_body_show_notes_with_report


@dataclass(frozen=True)
class EpisodeShowNoteRepair:
    episode_pk: int
    slug: str
    title: str
    body_changed: bool
    search_description_changed: bool
    source_detail_blocks_restored: int
    implicit_link_lists_converted: int
    implicit_link_list_headings_hidden: int
    implicit_link_lists_skipped: int
    support_copy_sections_restored: int
    raw_markdown_like: bool

    @property
    def has_reportable_action(self) -> bool:
        return (
            self.body_changed
            or self.search_description_changed
            or self.source_detail_blocks_restored > 0
            or self.implicit_link_lists_converted > 0
            or self.implicit_link_list_headings_hidden > 0
            or self.implicit_link_lists_skipped > 0
            or self.support_copy_sections_restored > 0
            or self.raw_markdown_like
        )


@dataclass(frozen=True)
class ShowNoteRepairResult:
    episodes_scanned: int = 0
    body_rows_changed: int = 0
    search_description_rows_changed: int = 0
    source_detail_blocks_restored: int = 0
    implicit_link_lists_converted: int = 0
    implicit_link_list_headings_hidden: int = 0
    implicit_link_lists_skipped: int = 0
    support_copy_sections_restored: int = 0
    raw_markdown_like_episodes: int = 0
    items: tuple[EpisodeShowNoteRepair, ...] = field(default_factory=tuple)


def repair_imported_episode_show_notes(
    *,
    Episode: Any,
    EpisodeSourceMetadata: Any,
    write: bool,
    collect_items: bool = True,
) -> ShowNoteRepairResult:
    """Repair imported episode bodies and summary metadata.

    The model classes are passed in so Django migrations can call the same
    logic with historical ORM models while the management command uses runtime
    models.
    """
    queryset = EpisodeSourceMetadata.objects.select_related("episode").order_by(
        "episode_number",
        "source_title",
    )

    if write:
        with transaction.atomic():
            return _repair_queryset(Episode, queryset, write=True, collect_items=collect_items)
    return _repair_queryset(Episode, queryset, write=False, collect_items=collect_items)


def _repair_queryset(
    Episode: Any,
    queryset: Any,
    *,
    write: bool,
    collect_items: bool,
) -> ShowNoteRepairResult:
    episodes_scanned = 0
    body_rows_changed = 0
    search_description_rows_changed = 0
    source_detail_blocks_restored = 0
    implicit_link_lists_converted = 0
    implicit_link_list_headings_hidden = 0
    implicit_link_lists_skipped = 0
    support_copy_sections_restored = 0
    raw_markdown_like_episodes = 0
    items: list[EpisodeShowNoteRepair] = []

    for metadata in queryset.iterator(chunk_size=100):
        episodes_scanned += 1
        episode = metadata.episode
        source_detail_html = episode_detail_for_body_from_database(episode, metadata)
        repaired_body, body_report = structure_episode_body_show_notes_with_report(
            episode.body,
            source_detail_html=source_detail_html,
        )
        desired_search_description = episode_summary_from_database(episode, metadata)
        current_search_description = getattr(episode, "search_description", "") or ""
        search_description_changed = (
            bool(desired_search_description)
            and current_search_description != desired_search_description
        )

        if body_report.changed:
            body_rows_changed += 1
        if search_description_changed:
            search_description_rows_changed += 1
        source_detail_blocks_restored += body_report.source_detail_blocks_restored
        implicit_link_lists_converted += body_report.implicit_link_lists_converted
        implicit_link_list_headings_hidden += body_report.implicit_link_list_headings_hidden
        implicit_link_lists_skipped += body_report.implicit_link_lists_skipped
        support_copy_sections_restored += body_report.support_copy_sections_restored
        if body_report.raw_markdown_like:
            raw_markdown_like_episodes += 1

        item = EpisodeShowNoteRepair(
            episode_pk=episode.pk,
            slug=getattr(episode, "slug", ""),
            title=getattr(episode, "title", ""),
            body_changed=body_report.changed,
            search_description_changed=search_description_changed,
            source_detail_blocks_restored=body_report.source_detail_blocks_restored,
            implicit_link_lists_converted=body_report.implicit_link_lists_converted,
            implicit_link_list_headings_hidden=body_report.implicit_link_list_headings_hidden,
            implicit_link_lists_skipped=body_report.implicit_link_lists_skipped,
            support_copy_sections_restored=body_report.support_copy_sections_restored,
            raw_markdown_like=body_report.raw_markdown_like,
        )
        if collect_items and item.has_reportable_action:
            items.append(item)

        if write:
            update_fields: dict[str, Any] = {}
            if body_report.changed:
                update_fields["body"] = repaired_body
            if search_description_changed:
                update_fields["search_description"] = desired_search_description
            if update_fields:
                Episode.objects.filter(pk=episode.pk).update(**update_fields)

    return ShowNoteRepairResult(
        episodes_scanned=episodes_scanned,
        body_rows_changed=body_rows_changed,
        search_description_rows_changed=search_description_rows_changed,
        source_detail_blocks_restored=source_detail_blocks_restored,
        implicit_link_lists_converted=implicit_link_lists_converted,
        implicit_link_list_headings_hidden=implicit_link_list_headings_hidden,
        implicit_link_lists_skipped=implicit_link_lists_skipped,
        support_copy_sections_restored=support_copy_sections_restored,
        raw_markdown_like_episodes=raw_markdown_like_episodes,
        items=tuple(items),
    )


def episode_summary_from_database(episode: Any, metadata: Any) -> str:
    summary = _summary_from_overview_body(episode)
    if summary:
        return summary

    summary = _plain_text(getattr(metadata, "simplecast_description", ""))
    if summary:
        return summary

    return _plain_text(getattr(metadata, "rss_description_html", ""))


def episode_detail_from_database(metadata: Any) -> str:
    detail = getattr(metadata, "simplecast_long_description_html", "")
    if detail:
        return detail
    return getattr(metadata, "rss_content_html", "")


def episode_detail_for_body_from_database(episode: Any, metadata: Any) -> str:
    detail = episode_detail_from_database(metadata)
    if not detail:
        return ""

    summary = episode_summary_from_database(episode, metadata)
    if summary and _plain_text(detail) == summary:
        return ""
    return detail


def _summary_from_overview_body(episode: Any) -> str:
    body = (
        episode.body.get_prep_value() if hasattr(episode.body, "get_prep_value") else episode.body
    )
    if not isinstance(body, list):
        return ""

    for block in body:
        if not isinstance(block, dict) or block.get("type") != "overview":
            continue
        children = block.get("value")
        if not isinstance(children, list):
            return ""
        summary_parts = [
            child["value"]
            for child in children
            if (
                isinstance(child, dict)
                and child.get("type") == "paragraph"
                and isinstance(child.get("value"), str)
            )
        ]
        return _plain_text(" ".join(summary_parts))

    return ""


def _plain_text(value: str) -> str:
    return " ".join(strip_tags(value).split())
