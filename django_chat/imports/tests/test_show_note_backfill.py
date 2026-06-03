from __future__ import annotations

from importlib import import_module
from io import StringIO
from typing import Any

import pytest
from cast.models import Episode
from django.apps import apps as django_apps
from django.core.management import call_command

from django_chat.imports.import_sample import import_django_chat_sample
from django_chat.imports.models import EpisodeSourceMetadata
from django_chat.imports.show_note_backfill import (
    episode_summary_from_database,
    repair_imported_episode_show_notes,
)

offload_migration = import_module(
    "django_chat.imports.migrations.0017_offload_raw_show_note_headings"
)
unhide_migration = import_module(
    "django_chat.imports.migrations.0018_unhide_implicit_link_list_headings"
)


@pytest.mark.django_db
def test_migration_0018_unhides_implicit_link_list_headings() -> None:
    import_django_chat_sample()
    metadata = EpisodeSourceMetadata.objects.get(episode_number=200)
    _isolate_metadata(metadata)
    episode = metadata.episode
    item = [{"title": "X", "url": "https://x.test", "description": "", "extra_links": []}]
    episode.body = [
        ("overview", [("paragraph", "Summary.")]),
        (
            "detail",
            [
                # Implicit link list with a hidden heading (old importer output).
                (
                    "show_note_link_list",
                    {
                        "heading": "Links",
                        "show_heading": False,
                        "kind": "auto",
                        "icon": "links",
                        "intro": "",
                        "items": item,
                    },
                ),
                # A list that already shows its heading is left alone.
                (
                    "show_note_link_list",
                    {
                        "heading": "Projects",
                        "kind": "auto",
                        "icon": "projects",
                        "intro": "",
                        "items": item,
                    },
                ),
                # A deliberately-hidden NON-implicit list (custom heading) must
                # stay hidden — only the generated implicit "Links" list is un-hidden.
                (
                    "show_note_link_list",
                    {
                        "heading": "Editor's Picks",
                        "show_heading": False,
                        "kind": "auto",
                        "icon": "links",
                        "intro": "",
                        "items": item,
                    },
                ),
            ],
        ),
    ]
    episode.save(update_fields=["body"])

    unhide_migration.unhide_implicit_link_list_headings(django_apps, None)

    episode.refresh_from_db()
    detail = _body_children(episode, "detail")
    # The hidden heading is un-hidden (key dropped -> default shows heading + icon);
    # heading/icon/items are untouched.
    assert "show_heading" not in detail[0]["value"]
    assert detail[0]["value"]["heading"] == "Links"
    assert detail[0]["value"]["icon"] == "links"
    assert len(detail[0]["value"]["items"]) == 1
    # The already-visible list is left exactly as-is.
    assert "show_heading" not in detail[1]["value"]
    # The deliberately-hidden custom list keeps its hidden heading.
    assert detail[2]["value"]["show_heading"] is False

    # Idempotent: a second run changes nothing.
    before = _body_children(episode, "detail")
    unhide_migration.unhide_implicit_link_list_headings(django_apps, None)
    episode.refresh_from_db()
    assert _body_children(episode, "detail") == before


@pytest.mark.django_db
def test_migration_0017_offloads_raw_headings_and_preserves_overrides() -> None:
    import_django_chat_sample()
    metadata = EpisodeSourceMetadata.objects.get(episode_number=200)
    _isolate_metadata(metadata)
    episode = metadata.episode
    item = [{"title": "X", "url": "https://x.test", "description": "", "extra_links": []}]
    episode.body = [
        ("overview", [("paragraph", "Summary.")]),
        (
            "detail",
            [
                # Raw, un-offloaded section heading: a Books list with prose after
                # the link is non-convertible, so pre-D5 it stayed as source HTML.
                (
                    "paragraph",
                    "<h3>📚 Books</h3>"
                    '<ul><li><a href="https://a.test/">Big Panda</a> by James Norbury</li></ul>',
                ),
                # An already-structured block carrying a genuine icon override must
                # survive: this is an in-place re-structure, not a source restore.
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

    offload_migration.offload_raw_show_note_headings(django_apps, None)

    episode.refresh_from_db()
    detail = _body_children(episode, "detail")
    # Raw "📚 Books" paragraph -> canonical iconed heading + the prose list kept.
    assert [c["type"] for c in detail] == [
        "show_note_heading",
        "paragraph",
        "show_note_link_list",
    ]
    assert detail[0]["value"]["heading"] == "Books"
    assert detail[0]["value"]["kind"] == "auto"
    assert detail[0]["value"]["icon"] == "books"
    assert "by James Norbury" in detail[1]["value"]
    # The override block is untouched (no source-based clobber).
    assert detail[2]["value"]["kind"] == "books"
    assert detail[2]["value"]["icon"] == "books"

    # Idempotent: a second run leaves the detail block unchanged.
    before = _body_children(episode, "detail")
    offload_migration.offload_raw_show_note_headings(django_apps, None)
    episode.refresh_from_db()
    assert _body_children(episode, "detail") == before


@pytest.mark.django_db
def test_show_note_repair_updates_body_and_search_description() -> None:
    import_django_chat_sample()
    metadata = EpisodeSourceMetadata.objects.get(episode_number=2)
    _isolate_metadata(metadata)
    episode = metadata.episode
    metadata.simplecast_long_description_html = (
        '<ul><li><a href="https://example.com/book">Book</a></li></ul>'
    )
    metadata.save(update_fields=["simplecast_long_description_html"])
    episode.body = [
        ("overview", [("paragraph", "<p>Short <strong>summary</strong>.</p>")]),
        (
            "detail",
            [
                (
                    "paragraph",
                    '<ul><li><a href="https://example.com/book">Book</a></li></ul>',
                )
            ],
        ),
    ]
    episode.search_description = "Book - note"
    episode.save(update_fields=["body", "search_description"])

    dry_run = repair_imported_episode_show_notes(
        Episode=Episode,
        EpisodeSourceMetadata=EpisodeSourceMetadata,
        write=False,
    )

    episode.refresh_from_db()
    assert dry_run.episodes_scanned == 1
    assert dry_run.body_rows_changed == 1
    assert dry_run.search_description_rows_changed == 1
    assert dry_run.implicit_link_lists_converted == 1
    assert episode.search_description == "Book - note"
    assert _body_children(episode, "detail")[0]["type"] == "paragraph"

    result = repair_imported_episode_show_notes(
        Episode=Episode,
        EpisodeSourceMetadata=EpisodeSourceMetadata,
        write=True,
    )

    episode.refresh_from_db()
    detail = _body_children(episode, "detail")
    assert result.body_rows_changed == 1
    assert result.search_description_rows_changed == 1
    assert detail[0]["type"] == "show_note_link_list"
    assert detail[0]["value"]["heading"] == "Links"
    assert "show_heading" not in detail[0]["value"]
    assert detail[0]["value"]["items"][0]["description"] == ""
    assert episode.search_description == "Short summary."

    second_run = repair_imported_episode_show_notes(
        Episode=Episode,
        EpisodeSourceMetadata=EpisodeSourceMetadata,
        write=True,
    )
    assert second_run.body_rows_changed == 0
    assert second_run.search_description_rows_changed == 0
    assert second_run.implicit_link_lists_converted == 0


@pytest.mark.django_db
def test_show_note_repair_restores_complex_source_detail_html() -> None:
    import_django_chat_sample()
    metadata = EpisodeSourceMetadata.objects.get(episode_number=2)
    _isolate_metadata(metadata)
    episode = metadata.episode
    metadata.simplecast_long_description_html = (
        "<h3>SHAMELESS PLUGS</h3>"
        "<ul>"
        '<li><a href="https://learndjango.com">LearnDjango</a> - Free tutorials</li>'
        '<li>Carlton\'s website <a href="https://noumenal.es/">Noumenal</a></li>'
        "</ul>"
    )
    metadata.save(update_fields=["simplecast_long_description_html"])
    episode.body = [
        ("overview", [("paragraph", "Short summary.")]),
        (
            "detail",
            [
                (
                    "show_note_link_list",
                    {
                        "heading": "Shameless Plugs",
                        "kind": "shameless_plugs",
                        "intro": "",
                        "items": [
                            {
                                "title": "LearnDjango",
                                "url": "https://learndjango.com",
                                "description": "",
                                "extra_links": [],
                            },
                            {
                                "title": "Noumenal",
                                "url": "https://noumenal.es/",
                                "description": "",
                                "extra_links": [],
                            },
                        ],
                    },
                )
            ],
        ),
    ]
    episode.search_description = "Short summary."
    episode.save(update_fields=["body", "search_description"])

    result = repair_imported_episode_show_notes(
        Episode=Episode,
        EpisodeSourceMetadata=EpisodeSourceMetadata,
        write=True,
    )

    episode.refresh_from_db()
    detail = _body_children(episode, "detail")
    assert result.body_rows_changed == 1
    assert result.source_detail_blocks_restored == 1
    # D5: the restored source heading is offloaded into an iconed heading block,
    # with the prose-prefixed list preserved verbatim as a following paragraph. The
    # known label canonicalizes the heading text ("SHAMELESS PLUGS" -> the label).
    assert [c["type"] for c in detail] == ["show_note_heading", "paragraph"]
    assert detail[0]["value"]["heading"] == "Shameless Plugs"
    assert detail[0]["value"]["icon"] == "shameless_plugs"
    assert "LearnDjango" in detail[1]["value"]
    assert "Noumenal" in detail[1]["value"]


@pytest.mark.django_db
def test_show_note_repair_shows_generated_links_heading_for_headingless_source() -> None:
    import_django_chat_sample()
    metadata = EpisodeSourceMetadata.objects.get(episode_number=2)
    _isolate_metadata(metadata)
    episode = metadata.episode
    metadata.simplecast_long_description_html = (
        '<ul><li><a href="https://example.com">Example</a></li></ul>'
    )
    metadata.save(update_fields=["simplecast_long_description_html"])
    episode.body = [
        ("overview", [("paragraph", "Short summary.")]),
        (
            "detail",
            [
                (
                    "show_note_link_list",
                    {
                        "heading": "Links",
                        "kind": "links",
                        "intro": "",
                        "items": [
                            {
                                "title": "Example",
                                "url": "https://example.com",
                                "description": "",
                                "extra_links": [],
                            }
                        ],
                    },
                )
            ],
        ),
    ]
    episode.search_description = "Short summary."
    episode.save(update_fields=["body", "search_description"])

    result = repair_imported_episode_show_notes(
        Episode=Episode,
        EpisodeSourceMetadata=EpisodeSourceMetadata,
        write=True,
    )

    episode.refresh_from_db()
    detail = _body_children(episode, "detail")
    assert result.body_rows_changed == 1
    assert result.source_detail_blocks_restored == 1
    assert result.implicit_link_list_headings_hidden == 0
    assert "show_heading" not in detail[0]["value"]


@pytest.mark.django_db
def test_show_note_repair_restores_support_paragraph_copy() -> None:
    import_django_chat_sample()
    metadata = EpisodeSourceMetadata.objects.get(episode_number=2)
    _isolate_metadata(metadata)
    episode = metadata.episode
    metadata.simplecast_long_description_html = (
        "<h3>Support the Show</h3>"
        '<p>Please visit <a href="https://learndjango.com">LearnDjango.com</a>, '
        '<a href="https://btn.dev/">Button</a>, or '
        '<a href="https://django-news.com">Django News</a>.</p>'
    )
    metadata.save(update_fields=["simplecast_long_description_html"])
    episode.body = [
        ("overview", [("paragraph", "Short summary.")]),
        (
            "detail",
            [
                (
                    "show_note_link_list",
                    {
                        "heading": "Support the Show",
                        "kind": "support",
                        "intro": "",
                        "items": [
                            {
                                "title": "LearnDjango.com",
                                "url": "https://learndjango.com",
                                "description": "",
                                "extra_links": [],
                            },
                            {
                                "title": "Button",
                                "url": "https://btn.dev/",
                                "description": "",
                                "extra_links": [],
                            },
                            {
                                "title": "Django News",
                                "url": "https://django-news.com",
                                "description": "",
                                "extra_links": [],
                            },
                        ],
                    },
                )
            ],
        ),
    ]
    episode.search_description = "Short summary."
    episode.save(update_fields=["body", "search_description"])

    result = repair_imported_episode_show_notes(
        Episode=Episode,
        EpisodeSourceMetadata=EpisodeSourceMetadata,
        write=True,
    )

    episode.refresh_from_db()
    detail = _body_children(episode, "detail")
    assert result.body_rows_changed == 1
    assert result.source_detail_blocks_restored == 1
    assert result.support_copy_sections_restored == 1
    # D5: the support heading is offloaded with an icon, its link copy preserved.
    assert [c["type"] for c in detail] == ["show_note_heading", "paragraph"]
    assert detail[0]["value"]["heading"] == "Support the Show"
    assert detail[0]["value"]["icon"] == "support"
    assert "Please visit" in detail[1]["value"]
    assert detail[1]["value"].count("href=") == 3


@pytest.mark.django_db
def test_show_note_repair_restores_support_boilerplate_copy() -> None:
    import_django_chat_sample()
    metadata = EpisodeSourceMetadata.objects.get(episode_number=2)
    _isolate_metadata(metadata)
    episode = metadata.episode
    metadata.simplecast_long_description_html = (
        "<h3>Support the Show</h3>"
        "<ul>"
        '<li><a href="http://learndjango.com">LearnDjango.com</a></li>'
        '<li><a href="https://btn.dev/">Button</a></li>'
        '<li><a href="https://django-news.com">Django News newsletter</a></li>'
        "</ul>"
    )
    metadata.save(update_fields=["simplecast_long_description_html"])
    episode.body = [
        ("overview", [("paragraph", "Short summary.")]),
        (
            "detail",
            [
                (
                    "show_note_link_list",
                    {
                        "heading": "Support the Show",
                        "kind": "support",
                        "intro": "",
                        "items": [
                            {
                                "title": "LearnDjango.com",
                                "url": "http://learndjango.com",
                                "description": "",
                                "extra_links": [],
                            },
                            {
                                "title": "Button",
                                "url": "https://btn.dev/",
                                "description": "",
                                "extra_links": [],
                            },
                            {
                                "title": "Django News newsletter",
                                "url": "https://django-news.com",
                                "description": "",
                                "extra_links": [],
                            },
                        ],
                    },
                )
            ],
        ),
    ]
    episode.search_description = "Short summary."
    episode.save(update_fields=["body", "search_description"])

    result = repair_imported_episode_show_notes(
        Episode=Episode,
        EpisodeSourceMetadata=EpisodeSourceMetadata,
        write=True,
    )

    episode.refresh_from_db()
    detail = _body_children(episode, "detail")
    assert result.body_rows_changed == 1
    assert result.source_detail_blocks_restored == 1
    assert result.support_copy_sections_restored == 1
    assert detail[0]["type"] == "show_note_link_list"
    assert detail[0]["value"]["kind"] == "auto"
    assert detail[0]["value"]["icon"] == "support"
    assert detail[0]["value"]["show_items"] is False
    assert "purchasing a book" in detail[0]["value"]["intro"]


@pytest.mark.django_db
def test_show_note_repair_reports_skipped_leading_list_and_raw_markdown() -> None:
    import_django_chat_sample()
    skipped_metadata = EpisodeSourceMetadata.objects.get(episode_number=2)
    markdown_metadata = EpisodeSourceMetadata.objects.get(episode_number=1)
    _isolate_metadata(skipped_metadata, markdown_metadata)
    skipped_episode = skipped_metadata.episode
    skipped_metadata.simplecast_long_description_html = (
        "<ul><li>No link here.</li><li><a>Missing href.</a></li></ul>"
    )
    skipped_metadata.save(update_fields=["simplecast_long_description_html"])
    skipped_episode.body = [
        ("overview", [("paragraph", "Short summary.")]),
        (
            "detail",
            [
                (
                    "show_note_link_list",
                    {
                        "heading": "Links",
                        "kind": "links",
                        "intro": "",
                        "items": [
                            {
                                "title": "Missing href.",
                                "url": "https://example.com",
                                "description": "",
                                "extra_links": [],
                            }
                        ],
                    },
                )
            ],
        ),
    ]
    skipped_episode.search_description = "Short summary."
    skipped_episode.save(update_fields=["body", "search_description"])

    markdown_episode = markdown_metadata.episode
    markdown_metadata.simplecast_long_description_html = (
        "* [Example](https://example.com)\n#### Links"
    )
    markdown_metadata.save(update_fields=["simplecast_long_description_html"])
    markdown_episode.body = [
        ("overview", [("paragraph", "Markdown summary.")]),
        ("detail", [("paragraph", "* [Example](https://example.com)#### Links")]),
    ]
    markdown_episode.search_description = "Markdown summary."
    markdown_episode.save(update_fields=["body", "search_description"])

    result = repair_imported_episode_show_notes(
        Episode=Episode,
        EpisodeSourceMetadata=EpisodeSourceMetadata,
        write=False,
    )

    assert result.body_rows_changed == 2
    assert result.implicit_link_lists_converted == 1
    assert result.implicit_link_lists_skipped == 1
    assert result.raw_markdown_like_episodes == 1
    skipped = {item.slug: item for item in result.items}
    assert skipped[skipped_episode.slug].source_detail_blocks_restored == 1
    assert skipped[skipped_episode.slug].implicit_link_lists_skipped == 1
    assert skipped[markdown_episode.slug].raw_markdown_like is True


@pytest.mark.django_db
def test_episode_summary_from_database_uses_metadata_fallbacks() -> None:
    import_django_chat_sample()
    metadata = EpisodeSourceMetadata.objects.get(episode_number=2)
    episode = metadata.episode
    episode.body = [("detail", [("paragraph", "Detail only.")])]
    metadata.simplecast_description = "<p>Simplecast summary.</p>"
    metadata.rss_description_html = "<p>RSS summary.</p>"

    assert episode_summary_from_database(episode, metadata) == "Simplecast summary."

    metadata.simplecast_description = ""
    assert episode_summary_from_database(episode, metadata) == "RSS summary."


@pytest.mark.django_db
def test_repair_show_notes_management_command_defaults_to_dry_run() -> None:
    import_django_chat_sample()
    metadata = EpisodeSourceMetadata.objects.get(episode_number=2)
    _isolate_metadata(metadata)
    episode = metadata.episode
    metadata.simplecast_long_description_html = (
        '<ul><li><a href="https://example.com">Example</a></li></ul>'
    )
    metadata.save(update_fields=["simplecast_long_description_html"])
    episode.body = [
        ("overview", [("paragraph", "Short summary.")]),
        (
            "detail",
            [("paragraph", '<ul><li><a href="https://example.com">Example</a></li></ul>')],
        ),
    ]
    episode.search_description = "Example"
    episode.save(update_fields=["body", "search_description"])

    stdout = StringIO()
    call_command("repair_django_chat_show_notes", stdout=stdout, verbosity=1)

    episode.refresh_from_db()
    assert "Dry-run show-note repair" in stdout.getvalue()
    assert "body_rows_changed=1" in stdout.getvalue()
    assert _body_children(episode, "detail")[0]["type"] == "paragraph"

    stdout = StringIO()
    call_command("repair_django_chat_show_notes", "--write", stdout=stdout, verbosity=1)

    episode.refresh_from_db()
    assert "Repaired" in stdout.getvalue()
    assert _body_children(episode, "detail")[0]["type"] == "show_note_link_list"
    assert episode.search_description == "Short summary."


def _body_children(episode: Any, block_type: str) -> list[dict[str, Any]]:
    body_data = episode.body.get_prep_value()
    for block in body_data:
        if block["type"] == block_type:
            return block["value"]
    msg = f"Episode body does not contain a {block_type!r} block."
    raise AssertionError(msg)


def _isolate_metadata(*metadata: EpisodeSourceMetadata) -> None:
    EpisodeSourceMetadata.objects.exclude(pk__in=[item.pk for item in metadata]).delete()
