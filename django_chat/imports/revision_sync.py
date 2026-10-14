"""Keep Wagtail's latest revision in step with out-of-band episode repairs.

Data repairs (migrations and repair commands) write directly to the live
``cast.Episode`` row. Wagtail's edit view, however, loads
``get_latest_revision_as_object()``, so a repair that only touches the live row
is silently reverted the next time an editor presses *Publish*.

This module reconciles the latest revision after such a write:

* **Published page, no pending draft** (``live`` and no unpublished changes,
  latest revision == live revision): the latest revision is a stale copy of what
  is live. The repaired fields are copied from the live row into that revision,
  so republishing it changes nothing.
* **Pending draft** (unpublished changes, or the latest revision is not the live
  one, or the page is not live): the draft is editor work and is never published
  or replaced by live values. An optional body transform (the same idempotent
  repair the live row received) is applied to the draft body in place, and the
  episode is reported as a divergent draft so an editor can review it.

Model classes are resolved through ``Episode._meta.apps`` so the same code works
with runtime models and with historical models inside data migrations.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from importlib import import_module
from typing import Any

from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction

BodyTransform = Callable[[list[Any]], tuple[list[Any], bool]]

# Fields that data repairs have rewritten on live episode rows.
REPAIRED_FIELDS = ("body", "search_description", "comments_enabled")

OUTCOME_NO_REVISION = "no_revision"
OUTCOME_IN_SYNC = "in_sync"
OUTCOME_SYNCED = "synced"
OUTCOME_DRAFT_REPAIRED = "draft_repaired"
OUTCOME_DRAFT_UNCHANGED = "draft_unchanged"
DRAFT_OUTCOMES = {OUTCOME_DRAFT_REPAIRED, OUTCOME_DRAFT_UNCHANGED}


@dataclass(frozen=True)
class DivergentDraft:
    episode_pk: int
    slug: str
    title: str
    body_repaired: bool
    differing_fields: tuple[str, ...]


@dataclass(frozen=True)
class RevisionSyncResult:
    episodes_scanned: int = 0
    without_revision: int = 0
    already_in_sync: int = 0
    revisions_synced: int = 0
    drafts_repaired: int = 0
    divergent_drafts: tuple[DivergentDraft, ...] = field(default_factory=tuple)


def sync_latest_revision(
    episode: Any,
    *,
    fields: tuple[str, ...] = REPAIRED_FIELDS,
    draft_body_transform: BodyTransform | None = None,
    write: bool = True,
) -> tuple[str, DivergentDraft | None]:
    """Reconcile ``episode``'s latest revision with its (already repaired) live row.

    ``episode`` must reflect the live row *after* the repair. Returns the outcome
    and, for pending drafts, a :class:`DivergentDraft` report entry.
    """
    revision = _latest_revision(episode)
    if revision is None:
        return OUTCOME_NO_REVISION, None

    content = revision.content if isinstance(revision.content, dict) else None
    if content is None:
        return OUTCOME_NO_REVISION, None

    if _is_pending_draft(episode, revision):
        return _repair_draft(episode, revision, content, fields, draft_body_transform, write)

    new_content = dict(content)
    changed = False
    for field_name in fields:
        if field_name not in content:
            continue
        live_value = _live_field_value(episode, field_name)
        if field_name == "body":
            if _strip_ids(_decode_body(content.get("body"))) == _strip_ids(live_value):
                continue
            new_content["body"] = _encode_body_like(content.get("body"), live_value)
        else:
            if content.get(field_name) == live_value:
                continue
            new_content[field_name] = live_value
        changed = True

    if not changed:
        return OUTCOME_IN_SYNC, None
    if write:
        type(revision).objects.filter(pk=revision.pk).update(content=new_content)
    return OUTCOME_SYNCED, None


def sync_episode_revisions(
    *,
    Episode: Any,
    EpisodeSourceMetadata: Any,
    write: bool,
) -> RevisionSyncResult:
    """Re-apply the earlier live-row repairs to every episode's latest revision.

    Published pages get their latest revision aligned with the live row (body,
    search description, comments flag). Pending drafts receive the idempotent
    body repairs from migrations 0013, 0015/0016 and 0018 in place, in an
    editor-safe form (unsafe markup only; icons only where none is stored), are
    never published, and are reported as divergent.
    """
    if write:
        with transaction.atomic():
            return _sync_episode_revisions(Episode, EpisodeSourceMetadata, write=True)
    return _sync_episode_revisions(Episode, EpisodeSourceMetadata, write=False)


def _sync_episode_revisions(
    Episode: Any, EpisodeSourceMetadata: Any, *, write: bool
) -> RevisionSyncResult:
    imported_ids = set(
        EpisodeSourceMetadata.objects.exclude(episode_id=None).values_list("episode_id", flat=True)
    )
    scanned = without_revision = in_sync = synced = drafts_repaired = 0
    divergent: list[DivergentDraft] = []

    for episode in Episode.objects.order_by("pk").iterator(chunk_size=100):
        scanned += 1
        transform = _draft_repair_pipeline(imported=episode.pk in imported_ids)
        outcome, draft = sync_latest_revision(episode, draft_body_transform=transform, write=write)
        if outcome == OUTCOME_NO_REVISION:
            without_revision += 1
        elif outcome == OUTCOME_IN_SYNC:
            in_sync += 1
        elif outcome == OUTCOME_SYNCED:
            synced += 1
        elif outcome == OUTCOME_DRAFT_REPAIRED:
            drafts_repaired += 1
        if draft is not None:
            divergent.append(draft)

    return RevisionSyncResult(
        episodes_scanned=scanned,
        without_revision=without_revision,
        already_in_sync=in_sync,
        revisions_synced=synced,
        drafts_repaired=drafts_repaired,
        divergent_drafts=tuple(divergent),
    )


def format_divergent_draft(draft: DivergentDraft) -> str:
    parts = ["body repaired" if draft.body_repaired else "body unchanged"]
    if draft.differing_fields:
        parts.append("differs from live: " + ", ".join(draft.differing_fields))
    return f"{draft.slug} (pk={draft.episode_pk}): {'; '.join(parts)} ({draft.title})"


def _draft_repair_pipeline(*, imported: bool) -> BodyTransform:
    """Draft-safe body repairs from migrations 0013, 0015/0016 and 0018, in order.

    Sanitizing and re-structuring (0013, 0017, 0018, 0019) were scoped to
    imported episodes; icon materialization (0015/0016) ran on every episode.
    Drafts are editor work, so the 0013 step only neutralizes unsafe markup
    (keeping Wagtail links/embeds), icons are only materialized on blocks
    without one, and the 0017/0019 re-structuring is skipped because it
    re-parses paragraph HTML and would drop editor RichText markup such as
    internal links. All steps are idempotent.
    """
    from django_chat.imports.show_note_backfill import neutralize_draft_body

    def pipeline(body: list[Any]) -> tuple[list[Any], bool]:
        changed = False
        if imported:
            body, step_changed = neutralize_draft_body(body)
            changed = changed or step_changed
        body, step_changed = materialize_body_icons(body, only_missing=True)
        changed = changed or step_changed
        if imported:
            body, step_changed = unhide_implicit_link_list_headings(body)
            changed = changed or step_changed
        return body, changed

    return pipeline


def materialize_body_icons(
    body: list[Any], *, only_missing: bool = False
) -> tuple[list[Any], bool]:
    """The 0015/0016 icon materialization applied to one body value.

    With ``only_missing`` only blocks that predate the icon model (no stored
    ``icon``) are touched, so explicit icon choices made in a current editor
    draft (including an intentional ``kind="links"``) are preserved.
    """
    icon_migration = import_module(
        "django_chat.imports.migrations.0015_materialize_show_note_icons"
    )
    from django_chat.imports.show_notes import resolve_icon_kind

    body = json.loads(json.dumps(body, cls=DjangoJSONEncoder))
    changed = False
    for section in body:
        if not isinstance(section, dict) or not isinstance(section.get("value"), list):
            continue
        for child in section["value"]:
            if (
                isinstance(child, dict)
                and child.get("type") in icon_migration.SHOW_NOTE_BLOCK_TYPES
                and not (
                    only_missing
                    and isinstance(child.get("value"), dict)
                    and child["value"].get("icon")
                )
                and icon_migration._materialize_block_value(
                    child.get("type"), child.get("value"), resolve_icon_kind
                )
            ):
                changed = True
    return body, changed


def unhide_implicit_link_list_headings(body: list[Any]) -> tuple[list[Any], bool]:
    """The 0018 un-hide of the generated implicit "Links" list on one body value."""
    body = json.loads(json.dumps(body, cls=DjangoJSONEncoder))
    changed = False
    for section in body:
        if (
            not isinstance(section, dict)
            or section.get("type") != "detail"
            or not isinstance(section.get("value"), list)
        ):
            continue
        for child in section["value"]:
            if (
                isinstance(child, dict)
                and child.get("type") == "show_note_link_list"
                and isinstance(child.get("value"), dict)
                and child["value"].get("show_heading") is False
                and child["value"].get("heading") == "Links"
            ):
                del child["value"]["show_heading"]
                changed = True
    return body, changed


def _repair_draft(
    episode: Any,
    revision: Any,
    content: dict[str, Any],
    fields: tuple[str, ...],
    draft_body_transform: BodyTransform | None,
    write: bool,
) -> tuple[str, DivergentDraft]:
    body_repaired = False
    new_content = dict(content)
    draft_body = _decode_body(content.get("body"))
    if draft_body_transform is not None and isinstance(draft_body, list):
        repaired_body, body_repaired = draft_body_transform(draft_body)
        if body_repaired:
            new_content["body"] = _encode_body_like(content.get("body"), repaired_body)
            if write:
                type(revision).objects.filter(pk=revision.pk).update(content=new_content)

    differing: list[str] = []
    for field_name in fields:
        live_value = _live_field_value(episode, field_name)
        if field_name == "body":
            if _strip_ids(_decode_body(new_content.get("body"))) != _strip_ids(live_value):
                differing.append(field_name)
        elif field_name in new_content and new_content.get(field_name) != live_value:
            differing.append(field_name)

    report = DivergentDraft(
        episode_pk=episode.pk,
        slug=getattr(episode, "slug", ""),
        title=getattr(episode, "title", ""),
        body_repaired=body_repaired,
        differing_fields=tuple(differing),
    )
    outcome = OUTCOME_DRAFT_REPAIRED if body_repaired else OUTCOME_DRAFT_UNCHANGED
    return outcome, report


def _latest_revision(episode: Any) -> Any | None:
    revision_id = getattr(episode, "latest_revision_id", None)
    if revision_id is None:
        return None
    try:
        Revision = episode._meta.apps.get_model("wagtailcore", "Revision")
    except LookupError:
        return None
    return Revision.objects.filter(pk=revision_id).first()


def _is_pending_draft(episode: Any, revision: Any) -> bool:
    return (
        not getattr(episode, "live", True)
        or bool(getattr(episode, "has_unpublished_changes", False))
        or getattr(episode, "live_revision_id", None) != revision.pk
    )


def _live_field_value(episode: Any, field_name: str) -> Any:
    value = getattr(episode, field_name)
    if field_name == "body":
        value = value.get_prep_value() if hasattr(value, "get_prep_value") else value
        if isinstance(value, str):
            value = json.loads(value)
        return json.loads(json.dumps(value, cls=DjangoJSONEncoder))
    return value


def _decode_body(raw: Any) -> Any:
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except ValueError:
            return raw
    return raw


def _encode_body_like(original: Any, body: list[Any]) -> Any:
    # Wagtail stores StreamField values in revision content as a JSON string
    # (StreamField.value_to_string); keep whichever shape the revision used.
    if isinstance(original, list):
        return body
    return json.dumps(body, cls=DjangoJSONEncoder)


def _strip_ids(value: Any) -> Any:
    """Compare StreamField data without block ids (regenerated when missing)."""
    if isinstance(value, list):
        return [_strip_ids(item) for item in value]
    if isinstance(value, dict):
        is_stream_child = "type" in value and "value" in value
        return {
            key: _strip_ids(item)
            for key, item in value.items()
            if not (is_stream_child and key == "id")
        }
    return value
