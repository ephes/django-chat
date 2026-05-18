from __future__ import annotations

from typing import Any

import pytest
from django.apps import apps
from django.conf import settings
from django.test import Client

from django_chat.imports.import_sample import import_django_chat_sample
from django_chat.imports.models import EpisodeSourceMetadata
from django_chat.imports.show_notes import normalize_episode_body_show_notes


def test_normalize_episode_body_show_notes_backfills_existing_detail_blocks() -> None:
    body = [
        {
            "type": "overview",
            "value": [
                {
                    "type": "paragraph",
                    "value": "<p>Links</p><ul><li>Overview should stay unchanged.</li></ul>",
                    "id": "overview-paragraph",
                }
            ],
            "id": "overview",
        },
        {
            "type": "detail",
            "value": [
                {
                    "type": "paragraph",
                    "value": (
                        "<p>🔗 Links</p>\n"
                        "<ul><li>Existing imported labels become headings.</li></ul>"
                        "<h4>SHAMELESS PLUGS</h4>"
                    ),
                    "id": "detail-paragraph",
                }
            ],
            "id": "detail",
        },
    ]

    normalized, changed = normalize_episode_body_show_notes(body)

    assert changed is True
    assert normalized[0]["value"][0]["value"] == body[0]["value"][0]["value"]
    assert normalized[1]["value"][0]["id"] == "detail-paragraph"
    assert "<h3>🔗 Links</h3>" in normalized[1]["value"][0]["value"]
    assert "<h3>SHAMELESS PLUGS</h3>" in normalized[1]["value"][0]["value"]
    assert "<p>🔗 Links</p>" not in normalized[1]["value"][0]["value"]
    assert "<h4>SHAMELESS PLUGS</h4>" not in normalized[1]["value"][0]["value"]


def test_normalize_episode_body_show_notes_reports_unchanged_body() -> None:
    body = [
        {
            "type": "detail",
            "value": [
                {
                    "type": "paragraph",
                    "value": "<p>Intro copy stays an ordinary paragraph.</p>",
                    "id": "detail-paragraph",
                }
            ],
            "id": "detail",
        },
    ]

    normalized, changed = normalize_episode_body_show_notes(body)

    assert changed is False
    assert normalized == body


@pytest.mark.django_db
def test_normalize_episode_body_show_notes_backfills_persisted_streamfield(
    client: Client,
) -> None:
    import_django_chat_sample()
    metadata = EpisodeSourceMetadata.objects.get(episode_number=200)
    episode = metadata.episode
    legacy_detail = (
        "<p>🔗 Links</p>"
        "<ul><li>Existing imported label becomes a heading.</li></ul>"
        "<h4>SHAMELESS PLUGS</h4>"
        "<ul><li>Legacy heading also becomes h3.</li></ul>"
    )
    episode.body = [
        ("overview", [("paragraph", "Overview stays untouched.")]),
        ("detail", [("paragraph", legacy_detail)]),
    ]
    episode.save(update_fields=["body"])

    Episode = apps.get_model("cast", "Episode")
    stale_episode = Episode.objects.only("pk", "body").get(pk=episode.pk)

    body, changed = normalize_episode_body_show_notes(stale_episode.body)
    assert changed is True
    Episode.objects.filter(pk=stale_episode.pk).update(body=body)

    backfilled_episode = Episode.objects.get(pk=episode.pk)
    detail = _body_block_html(backfilled_episode, "detail")
    assert "<h3>🔗 Links</h3>" in detail
    assert "<h3>SHAMELESS PLUGS</h3>" in detail
    assert "<p>🔗 Links</p>" not in detail
    assert "<h4>SHAMELESS PLUGS</h4>" not in detail

    response = client.get(f"/{settings.DJANGO_CHAT_PODCAST_SLUG}/{episode.slug}/")

    assert response.status_code == 200
    content = response.content.decode()
    assert "<h3>🔗 Links</h3>" in content
    assert "<h3>SHAMELESS PLUGS</h3>" in content


def _body_block_html(episode: Any, block_type: str) -> str:
    body_data = episode.body.get_prep_value()
    for block in body_data:
        if block["type"] == block_type:
            return "".join(
                child["value"] for child in block["value"] if child["type"] == "paragraph"
            )
    msg = f"Episode body does not contain a {block_type!r} block."
    raise AssertionError(msg)
