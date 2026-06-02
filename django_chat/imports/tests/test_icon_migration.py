from __future__ import annotations

from importlib import import_module

import pytest
from django.apps import apps as django_apps

from django_chat.imports.import_sample import import_django_chat_sample
from django_chat.imports.models import EpisodeSourceMetadata

migration = import_module("django_chat.imports.migrations.0015_materialize_show_note_icons")
migration_0016 = import_module("django_chat.imports.migrations.0016_heal_show_note_icons")


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
def test_migration_0015_legacy_links_default_follows_heading():
    """A link list left at the legacy kind="links" default but headed "Books" must
    normalise to auto and materialise the books icon, not freeze as a links override.
    The importer only ever emitted kind="links" alongside the heading "Links", so a
    "links" kind on a "Books" heading is the old ChoiceBlock default leaking through."""
    import_django_chat_sample()
    episode = EpisodeSourceMetadata.objects.get(episode_number=200).episode
    item = [{"title": "X", "url": "https://x.test", "description": "", "extra_links": []}]
    episode.body = [
        ("overview", [("paragraph", "Summary.")]),
        (
            "detail",
            [
                (
                    "show_note_link_list",
                    {"heading": "Books", "kind": "links", "intro": "", "items": item},
                ),
            ],
        ),
    ]
    episode.save(update_fields=["body"])

    migration.materialize_show_note_icons(django_apps, None)

    episode.refresh_from_db()
    block = _detail_children(episode)[0]["value"]
    assert block["kind"] == "auto"
    assert block["icon"] == "books"


@pytest.mark.django_db
def test_migration_0015_links_on_heading_block_is_a_real_override():
    """kind="links" only signals the legacy default on link-list blocks. Heading and
    sponsor blocks never had a concrete default, so a "links" there can only be a
    deliberate post-auto picker choice and must be preserved as an override."""
    import_django_chat_sample()
    episode = EpisodeSourceMetadata.objects.get(episode_number=200).episode
    episode.body = [
        ("overview", [("paragraph", "Summary.")]),
        ("detail", [("show_note_heading", {"heading": "Books", "kind": "links"})]),
    ]
    episode.save(update_fields=["body"])

    migration.materialize_show_note_icons(django_apps, None)

    episode.refresh_from_db()
    block = _detail_children(episode)[0]["value"]
    assert block["kind"] == "links"
    assert block["icon"] == "links"


@pytest.mark.django_db
def test_migration_0016_heals_link_lists_frozen_by_buggy_0015():
    """0016 re-runs the corrected backfill: link lists the initially-shipped 0015
    froze (default kind="links" kept as an icon override) follow their heading again,
    while genuine overrides survive the heal."""
    import_django_chat_sample()
    episode = EpisodeSourceMetadata.objects.get(episode_number=200).episode
    item = [{"title": "X", "url": "https://x.test", "description": "", "extra_links": []}]
    episode.body = [
        ("overview", [("paragraph", "Summary.")]),
        (
            "detail",
            [
                # Frozen by the buggy 0015: legacy default kept as a links override.
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
                # Genuine override must survive the heal.
                (
                    "show_note_link_list",
                    {
                        "heading": "Links",
                        "kind": "books",
                        "icon": "books",
                        "intro": "",
                        "items": item,
                    },
                ),
            ],
        ),
    ]
    episode.save(update_fields=["body"])

    migration_0016.Migration.operations[0].code(django_apps, None)

    episode.refresh_from_db()
    detail = _detail_children(episode)
    healed = detail[0]["value"]
    override = detail[1]["value"]
    assert (healed["kind"], healed["icon"]) == ("auto", "books")
    assert (override["kind"], override["icon"]) == ("books", "books")


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
