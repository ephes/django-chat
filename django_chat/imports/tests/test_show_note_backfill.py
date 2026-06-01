from __future__ import annotations

from io import StringIO
from typing import Any

import pytest
from cast.models import Episode
from django.core.management import call_command

from django_chat.imports.import_sample import import_django_chat_sample
from django_chat.imports.models import EpisodeSourceMetadata
from django_chat.imports.show_note_backfill import (
    episode_summary_from_database,
    repair_imported_episode_show_notes,
)


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
    assert detail[0]["value"]["show_heading"] is False
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
    assert detail[0]["type"] == "paragraph"
    assert detail[0]["value"] == metadata.simplecast_long_description_html


@pytest.mark.django_db
def test_show_note_repair_hides_existing_generated_links_heading() -> None:
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
    assert result.implicit_link_list_headings_hidden == 1
    assert detail[0]["value"]["show_heading"] is False


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
    assert detail[0]["type"] == "paragraph"
    assert detail[0]["value"] == metadata.simplecast_long_description_html


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
    assert detail[0]["value"]["kind"] == "support"
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
