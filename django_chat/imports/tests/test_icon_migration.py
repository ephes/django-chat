from __future__ import annotations

from importlib import import_module

import pytest
from django.apps import apps as django_apps

from django_chat.imports.import_sample import import_django_chat_sample
from django_chat.imports.models import EpisodeSourceMetadata

migration = import_module("django_chat.imports.migrations.0015_materialize_show_note_icons")


def _detail_children(episode):
    return [
        child
        for section in episode.body.get_prep_value()
        if section["type"] == "detail"
        for child in section["value"]
    ]


@pytest.mark.django_db
def test_migration_0015_materializes_icons_and_normalizes_kinds():
    import_django_chat_sample()
    episode = EpisodeSourceMetadata.objects.get(episode_number=200).episode
    item = [{"title": "X", "url": "https://x.test", "description": "", "extra_links": []}]
    episode.body = [
        ("overview", [("paragraph", "Summary.")]),
        (
            "detail",
            [
                # system-derived concrete kind (matches what the heading resolves to)
                (
                    "show_note_link_list",
                    {"heading": "Links", "kind": "links", "intro": "", "items": item},
                ),
                # auto heading block awaiting materialization
                ("show_note_heading", {"heading": "Black Friday Sale", "kind": "auto"}),
                # genuine editor override (kind diverges from the heading's auto result)
                (
                    "show_note_link_list",
                    {"heading": "Links", "kind": "books", "intro": "", "items": item},
                ),
            ],
        ),
    ]
    episode.save(update_fields=["body"])

    migration.materialize_show_note_icons(django_apps, None)

    episode.refresh_from_db()
    detail = _detail_children(episode)
    # system-derived "links" → normalized to auto, icon materialized
    assert detail[0]["value"]["kind"] == "auto"
    assert detail[0]["value"]["icon"] == "links"
    # auto heading → icon resolved from heading
    assert detail[1]["value"]["kind"] == "auto"
    assert detail[1]["value"]["icon"] == "sale"
    # genuine override preserved, icon set to the override
    assert detail[2]["value"]["kind"] == "books"
    assert detail[2]["value"]["icon"] == "books"


@pytest.mark.django_db
def test_migration_0015_is_idempotent():
    import_django_chat_sample()
    episode = EpisodeSourceMetadata.objects.get(episode_number=200).episode

    migration.materialize_show_note_icons(django_apps, None)
    episode.refresh_from_db()
    before = episode.body.get_prep_value()

    migration.materialize_show_note_icons(django_apps, None)
    episode.refresh_from_db()
    assert episode.body.get_prep_value() == before
