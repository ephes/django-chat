from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from django.db import transaction
from django.utils.html import strip_tags

from django_chat.imports.show_notes import (
    sanitize_show_note_html,
    structure_episode_body_show_notes_with_report,
)


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
    implicit_link_list_headings_added: int
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
            or self.implicit_link_list_headings_added > 0
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
    implicit_link_list_headings_added: int = 0
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
    implicit_link_list_headings_added = 0
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
        implicit_link_list_headings_added += body_report.implicit_link_list_headings_added
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
            implicit_link_list_headings_added=body_report.implicit_link_list_headings_added,
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
        implicit_link_list_headings_added=implicit_link_list_headings_added,
        implicit_link_lists_skipped=implicit_link_lists_skipped,
        support_copy_sections_restored=support_copy_sections_restored,
        raw_markdown_like_episodes=raw_markdown_like_episodes,
        items=tuple(items),
    )


def sanitize_imported_episode_bodies(
    *, Episode: Any, EpisodeSourceMetadata: Any, write: bool
) -> tuple[int, int]:
    """Sanitize the HTML in already-stored *imported* episode show-note bodies.

    Fresh imports sanitize on the way in, and the structuring repair only
    rewrites ``detail`` blocks — so previously-imported ``overview`` paragraph
    HTML and already-structured ``intro``/``copy`` values can still hold unsafe
    markup. This re-runs :func:`sanitize_show_note_html` over those
    RichText-bearing fields.

    Scoped to episodes that have ``EpisodeSourceMetadata`` (i.e. import-created
    bodies, matching :func:`repair_imported_episode_show_notes`). Manually
    authored episodes are left untouched — the sanitizer would otherwise strip
    Wagtail internal-link markup (``<a linktype="page" id="…">``) from
    editor-written rich text. Returns ``(episodes_scanned, bodies_changed)``.
    """
    queryset = EpisodeSourceMetadata.objects.select_related("episode").order_by(
        "episode_number",
        "source_title",
    )
    if write:
        with transaction.atomic():
            return _sanitize_bodies_queryset(Episode, queryset, write=True)
    return _sanitize_bodies_queryset(Episode, queryset, write=False)


def _sanitize_bodies_queryset(Episode: Any, queryset: Any, *, write: bool) -> tuple[int, int]:
    scanned = 0
    changed_count = 0
    for metadata in queryset.iterator(chunk_size=100):
        episode = metadata.episode
        if episode is None:
            continue
        scanned += 1
        new_body, changed = _sanitize_episode_body(episode.body)
        if not changed:
            continue
        changed_count += 1
        if write:
            Episode.objects.filter(pk=episode.pk).update(body=new_body)
    return scanned, changed_count


def _sanitize_episode_body(body: Any) -> tuple[Any, bool]:
    body_value = body.get_prep_value() if hasattr(body, "get_prep_value") else body
    if not isinstance(body_value, list):
        return body_value, False

    changed = False
    new_body: list[Any] = []
    for block in body_value:
        # Imported HTML only ever lands inside overview/detail show-note
        # containers; leave every other block type (images, embeds, …) alone.
        if (
            isinstance(block, dict)
            and block.get("type") in {"overview", "detail"}
            and isinstance(block.get("value"), list)
        ):
            new_children = []
            for child in block["value"]:
                new_child, child_changed = _sanitize_show_note_child(child)
                changed = changed or child_changed
                new_children.append(new_child)
            new_body.append({**block, "value": new_children})
        else:
            new_body.append(block)
    return new_body, changed


def _sanitize_show_note_child(child: Any) -> tuple[Any, bool]:
    if not isinstance(child, dict):
        return child, False
    child_type = child.get("type")
    value = child.get("value")
    if child_type == "paragraph" and isinstance(value, str):
        return _sanitized_str_child(child, value)
    if child_type == "show_note_link_list" and isinstance(value, dict):
        return _sanitized_link_list_child(child, value)
    if child_type == "show_note_sponsor" and isinstance(value, dict):
        return _sanitized_struct_field(child, value, "copy")
    return child, False


def _sanitized_str_child(child: dict[str, Any], value: str) -> tuple[Any, bool]:
    sanitized = sanitize_show_note_html(value)
    if sanitized == value:
        return child, False
    return {**child, "value": sanitized}, True


def _sanitized_struct_field(
    child: dict[str, Any], value: dict[str, Any], field_name: str
) -> tuple[Any, bool]:
    original = value.get(field_name)
    if not isinstance(original, str):
        return child, False
    sanitized = sanitize_show_note_html(original)
    if sanitized == original:
        return child, False
    return {**child, "value": {**value, field_name: sanitized}}, True


def _sanitized_link_list_child(child: dict[str, Any], value: dict[str, Any]) -> tuple[Any, bool]:
    new_value = dict(value)
    changed = False

    intro = value.get("intro")
    if isinstance(intro, str):
        sanitized_intro = sanitize_show_note_html(intro)
        if sanitized_intro != intro:
            new_value["intro"] = sanitized_intro
            changed = True

    items = value.get("items")
    if isinstance(items, list):
        new_items = []
        for item in items:
            if isinstance(item, dict) and isinstance(item.get("description"), str):
                sanitized_desc = sanitize_show_note_html(item["description"])
                if sanitized_desc != item["description"]:
                    new_items.append({**item, "description": sanitized_desc})
                    changed = True
                    continue
            new_items.append(item)
        if changed:
            new_value["items"] = new_items

    if not changed:
        return child, False
    return {**child, "value": new_value}, True


def drop_unsafe_source_links(*, PodcastSourceLink: Any, write: bool) -> tuple[int, int]:
    """Delete imported source links whose URL uses an unsafe scheme.

    Fresh imports skip non-http(s)/mailto link URLs (``_safe_link_url``); this
    remediates rows stored before that guard existed, where a ``javascript:``
    URL from a tampered upstream feed would otherwise render into a public
    ``<a href>``. Returns ``(links_scanned, links_removed)``.
    """
    from django_chat.imports.source_data import _safe_link_url

    scanned = 0
    unsafe_pks: list[Any] = []
    for link in PodcastSourceLink.objects.all().iterator(chunk_size=200):
        scanned += 1
        if _safe_link_url(link.url) is None:
            unsafe_pks.append(link.pk)
    if write and unsafe_pks:
        PodcastSourceLink.objects.filter(pk__in=unsafe_pks).delete()
    return scanned, len(unsafe_pks)


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
