"""Repairs written to live episode rows must survive the next Wagtail publish."""

from __future__ import annotations

import json
from importlib import import_module
from io import StringIO
from typing import Any

import pytest
from cast.models import Episode
from django.apps import apps as django_apps
from django.core.management import call_command

from django_chat.imports.import_sample import DownloadedAudio, import_django_chat_sample
from django_chat.imports.models import EpisodeSourceMetadata
from django_chat.imports.revision_sync import sync_episode_revisions
from django_chat.imports.show_note_backfill import sanitize_imported_episode_bodies

sync_migration = import_module("django_chat.imports.migrations.0021_sync_latest_episode_revisions")

UNSAFE_LINK = '<a href="javascript:alert(1)" onclick="y()">d</a>'
UNSAFE_HTML = '<p>Hi <a href="javascript:alert(1)" onclick="x()">there</a></p>'


def _fake_audio(source_url: str) -> DownloadedAudio:
    content = b"fake audio bytes"
    return DownloadedAudio(
        content=content,
        content_type="audio/mpeg",
        content_length=len(content),
        filename="sample.mp3",
    )


@pytest.fixture(autouse=True)
def _media_root(tmp_path, settings) -> None:
    settings.MEDIA_ROOT = tmp_path


def _import() -> None:
    # Episodes need audio to pass cast's publication policy.
    import_django_chat_sample(copy_audio=True, audio_downloader=_fake_audio)


def _body_with(html: str) -> list[Any]:
    return [
        ("overview", [("paragraph", "Summary.")]),
        ("detail", [("paragraph", html)]),
    ]


def _body_list(episode: Any) -> list[Any]:
    return json.loads(json.dumps(episode.body.get_prep_value()))


def _strip_ids(value: Any) -> Any:
    if isinstance(value, list):
        return [_strip_ids(item) for item in value]
    if isinstance(value, dict):
        return {k: _strip_ids(v) for k, v in value.items() if k != "id"}
    return value


def _revision_body(episode: Episode) -> list[Any]:
    revision = episode.get_latest_revision()
    assert revision is not None
    return _body_list(revision.as_object())


def _published_episode_with_stale_revision() -> Episode:
    """An imported episode an editor published, then a live-only repair."""
    _import()
    episode = EpisodeSourceMetadata.objects.get(episode_number=200).episode
    episode.body = _body_with(UNSAFE_HTML)
    episode.comments_enabled = False
    episode.save_revision().publish()
    episode.refresh_from_db()
    assert not episode.has_unpublished_changes

    # What migrations 0013/0020 did: rewrite the live row only.
    live_body = _body_list(episode)
    live_body[1]["value"][0]["value"] = '<p>Hi <a rel="nofollow">there</a></p>'
    Episode.objects.filter(pk=episode.pk).update(body=live_body, comments_enabled=True)
    episode.refresh_from_db()
    return episode


@pytest.mark.django_db
def test_migration_aligns_latest_revision_so_republish_changes_nothing() -> None:
    episode = _published_episode_with_stale_revision()
    live_body = _body_list(episode)
    assert "javascript:" in json.dumps(_revision_body(episode))

    sync_migration.sync_latest_episode_revisions(django_apps, None)

    episode.refresh_from_db()
    assert _strip_ids(_revision_body(episode)) == _strip_ids(live_body)
    assert episode.get_latest_revision_as_object().comments_enabled is True

    # Editor opens the page and presses Publish without changes.
    episode.get_latest_revision_as_object().save_revision().publish()
    episode.refresh_from_db()
    assert _strip_ids(_body_list(episode)) == _strip_ids(live_body)
    assert "javascript:" not in json.dumps(_body_list(episode))
    assert episode.comments_enabled is True


@pytest.mark.django_db
def test_sync_is_idempotent() -> None:
    episode = _published_episode_with_stale_revision()

    first = sync_episode_revisions(
        Episode=Episode, EpisodeSourceMetadata=EpisodeSourceMetadata, write=True
    )
    revision = Episode.objects.get(pk=episode.pk).get_latest_revision()
    content_after_first = revision.content
    second = sync_episode_revisions(
        Episode=Episode, EpisodeSourceMetadata=EpisodeSourceMetadata, write=True
    )

    assert first.revisions_synced == 1
    assert second.revisions_synced == 0
    assert second.already_in_sync == 1
    revision.refresh_from_db()
    assert revision.content == content_after_first


@pytest.mark.django_db
def test_dry_run_writes_nothing() -> None:
    episode = _published_episode_with_stale_revision()
    revision = episode.get_latest_revision()
    before = revision.content

    result = sync_episode_revisions(
        Episode=Episode, EpisodeSourceMetadata=EpisodeSourceMetadata, write=False
    )

    assert result.revisions_synced == 1
    revision.refresh_from_db()
    assert revision.content == before


@pytest.mark.django_db
def test_pending_draft_is_repaired_in_place_reported_and_never_published() -> None:
    _import()
    episode = EpisodeSourceMetadata.objects.get(episode_number=200).episode
    episode.save_revision().publish()
    episode.refresh_from_db()
    live_revision_id = episode.live_revision_id
    live_title = episode.title
    live_body = _body_list(episode)

    # Editor saves (but does not publish) a draft with a new title and unsafe HTML.
    draft = episode.get_latest_revision_as_object()
    draft.title = "Editor draft title"
    draft.body = _body_with(UNSAFE_HTML)
    draft_revision = draft.save_revision()

    result = sync_episode_revisions(
        Episode=Episode, EpisodeSourceMetadata=EpisodeSourceMetadata, write=True
    )

    episode.refresh_from_db()
    # Live row and publish state untouched.
    assert episode.title == live_title
    assert _strip_ids(_body_list(episode)) == _strip_ids(live_body)
    assert episode.live_revision_id == live_revision_id
    assert episode.has_unpublished_changes
    assert episode.latest_revision_id == draft_revision.pk

    # Draft keeps the editor's work, minus the unsafe markup.
    draft_object = episode.get_latest_revision_as_object()
    assert draft_object.title == "Editor draft title"
    assert "javascript:" not in json.dumps(_body_list(draft_object))
    assert "onclick" not in json.dumps(_body_list(draft_object))

    assert result.drafts_repaired == 1
    assert [d.episode_pk for d in result.divergent_drafts] == [episode.pk]
    assert result.divergent_drafts[0].body_repaired
    assert "body" in result.divergent_drafts[0].differing_fields

    # Re-running reports the draft again but does not change it further.
    again = sync_episode_revisions(
        Episode=Episode, EpisodeSourceMetadata=EpisodeSourceMetadata, write=True
    )
    assert again.drafts_repaired == 0
    assert [d.episode_pk for d in again.divergent_drafts] == [episode.pk]


@pytest.mark.django_db
def test_episodes_without_revisions_are_left_alone() -> None:
    _import()

    result = sync_episode_revisions(
        Episode=Episode, EpisodeSourceMetadata=EpisodeSourceMetadata, write=True
    )

    assert result.episodes_scanned == Episode.objects.count()
    assert result.without_revision == result.episodes_scanned
    assert result.revisions_synced == 0


@pytest.mark.django_db
def test_sanitize_backfill_keeps_latest_revision_in_step() -> None:
    _import()
    episode = EpisodeSourceMetadata.objects.get(episode_number=200).episode
    episode.body = _body_with(UNSAFE_HTML)
    episode.save_revision().publish()

    sanitize_imported_episode_bodies(
        Episode=Episode, EpisodeSourceMetadata=EpisodeSourceMetadata, write=True
    )

    episode.refresh_from_db()
    assert "javascript:" not in json.dumps(_body_list(episode))
    assert _strip_ids(_revision_body(episode)) == _strip_ids(_body_list(episode))


@pytest.mark.django_db
def test_sanitize_backfill_repairs_pending_draft_without_publishing() -> None:
    _import()
    episode = EpisodeSourceMetadata.objects.get(episode_number=200).episode
    episode.save_revision().publish()
    episode.refresh_from_db()
    live_revision_id = episode.live_revision_id
    draft = episode.get_latest_revision_as_object()
    draft.body = _body_with(UNSAFE_HTML)
    draft.save_revision()

    sanitize_imported_episode_bodies(
        Episode=Episode, EpisodeSourceMetadata=EpisodeSourceMetadata, write=True
    )

    episode.refresh_from_db()
    assert episode.live_revision_id == live_revision_id
    assert episode.has_unpublished_changes
    assert "javascript:" not in json.dumps(_revision_body(episode))


@pytest.mark.django_db
def test_command_reports_divergent_drafts_and_defaults_to_dry_run() -> None:
    _import()
    episode = EpisodeSourceMetadata.objects.get(episode_number=200).episode
    episode.save_revision().publish()
    episode.refresh_from_db()
    draft = episode.get_latest_revision_as_object()
    draft.body = _body_with(UNSAFE_HTML)
    draft_revision = draft.save_revision()
    draft_revision.refresh_from_db()
    before = draft_revision.content

    stdout = StringIO()
    call_command("sync_django_chat_episode_revisions", stdout=stdout)

    output = stdout.getvalue()
    assert "Dry-run episode revision sync" in output
    assert "divergent_drafts=1" in output
    assert f"(pk={episode.pk})" in output
    draft_revision.refresh_from_db()
    assert draft_revision.content == before


@pytest.mark.django_db
def test_migration_works_with_historical_models() -> None:
    from django.db import connection
    from django.db.migrations.executor import MigrationExecutor

    episode = _published_episode_with_stale_revision()
    live_body = _body_list(episode)
    historical_apps = (
        MigrationExecutor(connection)
        .loader.project_state([("imports", "0021_sync_latest_episode_revisions")])
        .apps
    )

    sync_migration.sync_latest_episode_revisions(historical_apps, None)

    episode.refresh_from_db()
    assert _strip_ids(_revision_body(episode)) == _strip_ids(live_body)
    assert episode.get_latest_revision_as_object().comments_enabled is True


@pytest.mark.django_db
def test_draft_repair_keeps_editor_rich_text_and_icon_overrides() -> None:
    _import()
    episode = EpisodeSourceMetadata.objects.get(episode_number=200).episode
    episode.save_revision().publish()
    episode.refresh_from_db()
    item = [{"title": "X", "url": "https://x.test", "description": "", "extra_links": []}]
    draft = episode.get_latest_revision_as_object()
    draft.body = [
        ("overview", [("paragraph", "Summary.")]),
        (
            "detail",
            [
                (
                    "paragraph",
                    '<p>See <a linktype="page" id="1">About</a> and '
                    '<a href="javascript:alert(1)">bad</a>.</p>'
                    '<embed embedtype="image" id="3" format="left" alt="x"/>',
                ),
                # Explicit editor icon choice on a current draft.
                (
                    "show_note_link_list",
                    {
                        "heading": "Books",
                        "kind": "links",
                        "icon": "links",
                        "intro": "",
                        "items": item,
                    },
                ),
            ],
        ),
    ]
    draft.save_revision()

    sync_episode_revisions(Episode=Episode, EpisodeSourceMetadata=EpisodeSourceMetadata, write=True)

    episode.refresh_from_db()
    stored = json.dumps(_revision_body(episode))
    assert 'linktype=\\"page\\"' in stored
    assert 'id=\\"1\\"' in stored
    assert 'embedtype=\\"image\\"' in stored
    assert "javascript:" not in stored
    detail = [
        child
        for section in _revision_body(episode)
        if section["type"] == "detail"
        for child in section["value"]
    ]
    link_list = next(c for c in detail if c["type"] == "show_note_link_list")
    assert link_list["value"]["kind"] == "links"
    assert link_list["value"]["icon"] == "links"


@pytest.mark.parametrize(
    ("html", "kept", "removed"),
    [
        ('<p><a linktype="page" id="4">x</a></p>', ['linktype="page"', 'id="4"'], []),
        ('<p><a href="https://ok.test">x</a></p>', ['href="https://ok.test"'], []),
        ('<p><a href=" JaVa\tScript:alert(1)">x</a></p>', ["<a>x</a>"], ["alert"]),
        ('<p onclick="x()" style="color:red">t</p>', ["<p>t</p>"], ["onclick", "style"]),
        ("<p>a</p><script>alert(1)</script>", ["<p>a</p>"], ["script"]),
        ('<embed embedtype="image" id="3"/>', ['embedtype="image"'], []),
        ('<embed src="data:text/html,x"/>', [], ["embed"]),
    ],
)
def test_neutralize_unsafe_html(html: str, kept: list[str], removed: list[str]) -> None:
    from django_chat.imports.show_notes import neutralize_unsafe_html

    result = neutralize_unsafe_html(html)
    for fragment in kept:
        assert fragment in result
    for fragment in removed:
        assert fragment not in result.lower()


def test_neutralize_keeps_wagtail_double_quoted_attributes() -> None:
    from django_chat.imports.show_notes import neutralize_unsafe_html

    html = (
        '<p onclick="x()">t</p>'
        '<embed alt="A &quot;quoted&quot; caption" embedtype="image" format="left" id="3"/>'
    )
    result = neutralize_unsafe_html(html)
    assert "onclick" not in result
    assert 'alt="A &quot;quoted&quot; caption"' in result
    assert "'" not in result


def test_draft_sanitizer_handles_wagtail_wrapped_list_items() -> None:
    from django_chat.imports.show_note_backfill import neutralize_draft_body

    body = [
        {
            "type": "detail",
            "value": [
                {
                    "type": "show_note_link_list",
                    "value": {
                        "heading": "Links",
                        "intro": "",
                        "items": [
                            {
                                "type": "item",
                                "id": "keep-me",
                                "value": {
                                    "title": "X",
                                    "url": "https://x.test",
                                    "description": UNSAFE_LINK,
                                    "extra_links": [],
                                },
                            }
                        ],
                    },
                    "id": "list-id",
                }
            ],
        }
    ]

    new_body, changed = neutralize_draft_body(body)

    assert changed
    item = new_body[0]["value"][0]["value"]["items"][0]
    assert item["id"] == "keep-me"
    assert item["type"] == "item"
    assert "javascript" not in item["value"]["description"]
    assert "onclick" not in item["value"]["description"]
