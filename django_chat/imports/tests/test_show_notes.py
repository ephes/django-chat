from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from bs4 import BeautifulSoup
from django.apps import apps
from django.conf import settings
from django.template.loader import render_to_string
from django.test import Client, RequestFactory

from django_chat.imports.import_sample import import_django_chat_sample
from django_chat.imports.models import EpisodeSourceMetadata
from django_chat.imports.show_notes import (
    normalize_episode_body_show_notes,
    structure_episode_body_show_notes,
    structured_show_note_detail_blocks,
)
from django_chat.show_notes.blocks import link_list_block, sponsor_block


def test_show_note_blocks_are_registered_for_detail_only() -> None:
    from cast.post_body_blocks import (
        DEFAULT_CONTENT_BLOCK_NAMES,
        configured_content_blocks,
        validate_post_body_block_setting,
    )

    detail_blocks = configured_content_blocks("detail")
    overview_blocks = configured_content_blocks("overview")
    detail_block_names = {name for name, _block in detail_blocks}

    assert {"show_note_sponsor", "show_note_link_list"} <= detail_block_names
    assert all(name not in DEFAULT_CONTENT_BLOCK_NAMES for name in detail_block_names)
    assert "show_note_sponsor" not in {name for name, _block in overview_blocks}
    assert "show_note_link_list" not in {name for name, _block in overview_blocks}
    assert validate_post_body_block_setting() == []


def test_show_note_block_factories_return_stable_block_names() -> None:
    sponsor_name, sponsor = sponsor_block()
    link_list_name, link_list = link_list_block()

    assert sponsor_name == "show_note_sponsor"
    assert sponsor.meta.icon == "tag"
    assert sponsor.meta.label == "Show-note sponsor"
    assert link_list_name == "show_note_link_list"
    assert link_list.meta.icon == "link"
    assert link_list.meta.label == "Show-note link list"


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


def test_structured_show_note_detail_blocks_convert_rich_recent_sections() -> None:
    html = (
        "<p>🔗 Links</p>"
        '<ul><li><a href="https://example.com/one">Primary</a> and '
        '<a href="https://example.com/two">Secondary</a></li></ul>'
        "<p>📦 Projects</p>"
        '<ul><li><a href="https://example.com/project">Project</a></li></ul>'
        "<p>📚 Books</p>"
        '<ul><li><a href="https://example.com/book">Book by Author</a></li></ul>'
        "<p>🎥 YouTube</p>"
        '<ul><li><a href="https://www.youtube.com/@djangochat">YouTube</a></li></ul>'
        "<p>🤝 Sponsor</p>"
        '<p>Sponsored by <a href="https://buttondown.com/django">Buttondown</a>.</p>'
    )

    blocks, changed = structured_show_note_detail_blocks(html)

    assert changed is True
    assert [name for name, _value in blocks] == [
        "show_note_link_list",
        "show_note_link_list",
        "show_note_link_list",
        "show_note_link_list",
        "show_note_sponsor",
    ]
    links = blocks[0][1]
    assert links["heading"] == "Links"
    assert links["kind"] == "links"
    assert links["items"][0]["title"] == "Primary"
    assert links["items"][0]["extra_links"] == [
        {"title": "Secondary", "url": "https://example.com/two"}
    ]
    assert blocks[1][1]["kind"] == "projects"
    assert blocks[2][1]["kind"] == "books"
    assert blocks[2][1]["items"][0]["title"] == "Book by Author"
    assert blocks[3][1]["kind"] == "youtube"
    sponsor = blocks[4][1]
    assert sponsor["heading"] == "Sponsor"
    assert sponsor["sponsor_name"] == "Buttondown"
    assert sponsor["sponsor_url"] == "https://buttondown.com/django"
    assert "Sponsored by" in sponsor["copy"]


def test_structured_show_note_detail_blocks_convert_legacy_kind_variants() -> None:
    html = (
        "<p>###Support the Show</p>"
        '<p>Support us on <a href="https://example.com/support">Patreon</a>.</p>'
        "<h4>SHAMELESS PLUGS</h4>"
        '<ul><li><a href="https://example.com/plug">Plug</a></li></ul>'
        "<h3>Groups</h3>"
        '<ul><li><a href="https://example.com/group">Group</a></li></ul>'
        "<h3>Sponsors</h3>"
        '<ul><li><a href="https://example.com/sponsor">Sponsor option</a></li></ul>'
        "<h3>Sponsoring Options</h3>"
        '<ul><li><a href="revsys.com">REVSYS</a></li></ul>'
    )

    blocks, changed = structured_show_note_detail_blocks(html)

    assert changed is True
    assert [value["kind"] for name, value in blocks if name == "show_note_link_list"] == [
        "support",
        "shameless_plugs",
        "groups",
        "sponsors",
        "sponsoring_options",
    ]
    support = blocks[0][1]
    assert support["intro"] == ""
    assert support["items"][0]["title"] == "Support us on Patreon."
    assert support["items"][0]["url"] == "https://example.com/support"
    assert blocks[-1][1]["items"][0]["url"] == "https://revsys.com"


def test_support_paragraph_renders_without_duplicate_link() -> None:
    blocks, changed = structured_show_note_detail_blocks(
        "<p>Support the Show</p>"
        '<p>Support us on <a href="https://example.com/support">Patreon</a>.</p>'
    )

    assert changed is True
    assert blocks[0][0] == "show_note_link_list"
    html = render_to_string(
        "cast/django_chat/show_notes/link_list.html",
        {
            "value": _template_value(blocks[0][1]),
            "render_for_feed": False,
        },
    )

    assert 'class="show-note-intro"' not in html
    assert html.count('href="https://example.com/support"') == 1
    assert "Support us on Patreon." in html


def test_multi_link_sponsor_list_stays_unstructured() -> None:
    html = (
        "<p>Sponsor</p>"
        "<ul>"
        '<li><a href="https://example.com/one">One</a></li>'
        '<li><a href="https://example.com/two">Two</a></li>'
        "</ul>"
    )

    blocks, changed = structured_show_note_detail_blocks(html)

    assert changed is True
    assert blocks == [
        (
            "paragraph",
            "<h3>Sponsor</h3>"
            "<ul>"
            '<li><a href="https://example.com/one">One</a></li>'
            '<li><a href="https://example.com/two">Two</a></li>'
            "</ul>",
        )
    ]


def test_structured_show_note_detail_blocks_preserve_unsupported_sections() -> None:
    html = (
        "<p>Intro copy stays.</p><h3>Links</h3><ul><li>Missing link stays unstructured.</li></ul>"
    )

    blocks, changed = structured_show_note_detail_blocks(html)

    assert changed is False
    assert blocks == [
        (
            "paragraph",
            "<p>Intro copy stays.</p>"
            "<h3>Links</h3>"
            "<ul><li>Missing link stays unstructured.</li></ul>",
        )
    ]


def test_structure_episode_body_show_notes_is_idempotent() -> None:
    body = [
        {
            "type": "detail",
            "value": [
                {
                    "type": "paragraph",
                    "value": (
                        '<p>🔗 Links</p><ul><li><a href="https://example.com">Example</a></li></ul>'
                    ),
                    "id": "detail-paragraph",
                }
            ],
            "id": "detail",
        },
    ]

    structured, changed = structure_episode_body_show_notes(body)
    structured_again, changed_again = structure_episode_body_show_notes(structured)

    assert changed is True
    assert structured[0]["value"][0]["type"] == "show_note_link_list"
    assert changed_again is False
    assert structured_again == structured


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


@pytest.mark.django_db
def test_structured_show_notes_render_on_public_episode_detail(client: Client) -> None:
    import_django_chat_sample()
    metadata = EpisodeSourceMetadata.objects.get(episode_number=200)

    response = client.get(f"/{settings.DJANGO_CHAT_PODCAST_SLUG}/{metadata.episode.slug}/")

    assert response.status_code == 200
    content = response.content.decode()
    assert "show-note-block" not in content
    assert 'class="show-note-icon show-note-icon--links"' in content
    assert 'class="show-note-icon show-note-icon--projects"' in content
    assert 'class="show-note-icon show-note-icon--books"' in content
    assert 'class="show-note-icon show-note-icon--youtube"' in content
    assert 'class="show-note-icon show-note-icon--sponsor"' in content
    assert "show-note-primary-link" not in content
    assert "show-note-extra-links" not in content
    assert '<ul role="list">' in content
    assert '<a href="https://github.com/RealOrangeOne/django-tasks">django-tasks</a>' in content
    soup = BeautifulSoup(content, "html.parser")
    show_notes = soup.select_one(".show-notes")
    assert show_notes is not None
    headings = [heading.get_text(strip=True) for heading in show_notes.select("h3")]
    assert headings[:5] == ["Links", "Projects", "Books", "YouTube", "Sponsor"]
    github_links = show_notes.select('a[href="https://github.com/realorangeone"]')
    assert any(
        link.get_text(strip=True) == "Jake's GitHub"
        and link.parent is not None
        and link.parent.name == "li"
        for link in github_links
    )
    assert "This episode was brought to you by" in content
    assert 'href="https://buttondown.com/django"' in content


@pytest.mark.django_db
def test_structured_show_notes_render_feed_safe_html() -> None:
    import_django_chat_sample()
    metadata = EpisodeSourceMetadata.objects.get(episode_number=200)
    request = RequestFactory(HTTP_HOST="testserver").get(f"/episodes/{metadata.episode.slug}/")

    content = metadata.episode.get_description(
        request=request,
        render_detail=True,
        render_for_feed=True,
        escape_html=False,
        remove_newlines=False,
    )

    assert "show-note-icon" not in content
    assert "show-note-block" not in content
    assert "<h3>Links</h3>" in content
    assert "django-tasks" in content
    assert "Buttondown" in content


def _body_block_html(episode: Any, block_type: str) -> str:
    body_data = episode.body.get_prep_value()
    for block in body_data:
        if block["type"] == block_type:
            return "".join(
                child["value"] for child in block["value"] if child["type"] == "paragraph"
            )
    msg = f"Episode body does not contain a {block_type!r} block."
    raise AssertionError(msg)


def _template_value(value: Any) -> Any:
    if isinstance(value, dict):
        return SimpleNamespace(**{key: _template_value(item) for key, item in value.items()})
    if isinstance(value, list):
        return [_template_value(item) for item in value]
    return value
