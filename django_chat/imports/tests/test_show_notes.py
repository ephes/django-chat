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
    structure_episode_body_show_notes_with_report,
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


def test_structured_show_note_detail_blocks_preserve_complex_link_sections() -> None:
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
    # The Links section has a non-convertible multi-anchor item, so D5 offloads
    # the heading (with an icon) and preserves the list verbatim as a paragraph.
    assert [name for name, _value in blocks] == [
        "show_note_heading",
        "paragraph",
        "show_note_link_list",
        "show_note_link_list",
        "show_note_link_list",
        "show_note_sponsor",
    ]
    assert blocks[0][1]["heading"] == "🔗 Links"
    assert blocks[0][1]["kind"] == "auto"
    assert blocks[0][1]["icon"] == "links"
    assert blocks[1][1] == (
        '<ul><li><a href="https://example.com/one">Primary</a> and '
        '<a href="https://example.com/two">Secondary</a></li></ul>'
    )
    assert blocks[2][1]["kind"] == "auto"
    assert blocks[2][1]["icon"] == "projects"
    assert blocks[3][1]["icon"] == "books"
    assert blocks[3][1]["items"][0]["title"] == "Book by Author"
    assert blocks[4][1]["icon"] == "youtube"
    sponsor = blocks[5][1]
    assert sponsor["heading"] == "Sponsor"
    assert sponsor["kind"] == "auto"
    assert sponsor["icon"] == "sponsor"
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
    # All structured link lists store kind="auto"; the icon carries the label.
    assert all(value["kind"] == "auto" for name, value in blocks if name == "show_note_link_list")
    assert [value["icon"] for name, value in blocks if name == "show_note_link_list"] == [
        "shameless_plugs",
        "groups",
        "sponsors",
        "sponsoring_options",
    ]
    # D5: the paragraph-only "Support the Show" heading is offloaded with an icon,
    # its copy preserved verbatim as a following paragraph block.
    assert blocks[0][0] == "show_note_heading"
    assert blocks[0][1]["heading"] == "Support the Show"
    assert blocks[0][1]["icon"] == "support"
    assert blocks[1] == (
        "paragraph",
        '<p>Support us on <a href="https://example.com/support">Patreon</a>.</p>',
    )
    assert blocks[-1][1]["items"][0]["url"] == "https://revsys.com"


def test_support_paragraph_preserves_embedded_link_copy() -> None:
    blocks, changed = structured_show_note_detail_blocks(
        "<p>Support the Show</p>"
        '<p>Support us on <a href="https://example.com/support">Patreon</a>.</p>'
    )

    assert changed is True
    # D5 offloads the heading (with an icon) and keeps the link copy verbatim.
    assert blocks[0][0] == "show_note_heading"
    assert blocks[0][1]["heading"] == "Support the Show"
    assert blocks[0][1]["icon"] == "support"
    assert blocks[1] == (
        "paragraph",
        '<p>Support us on <a href="https://example.com/support">Patreon</a>.</p>',
    )
    copy_html = blocks[1][1]
    assert copy_html.count('href="https://example.com/support"') == 1
    assert BeautifulSoup(copy_html, "html.parser").get_text(" ", strip=True) == (
        "Support us on Patreon ."
    )


def test_markdown_prefixed_support_heading_normalizes_without_hashes() -> None:
    blocks, changed = structured_show_note_detail_blocks(
        "<h3>###Support the Show</h3>"
        '<p>Support us on <a href="https://example.com/support">Patreon</a>.</p>'
    )

    assert changed is True
    # The markdown "###" prefix is stripped; D5 offloads the cleaned heading.
    assert blocks[0][0] == "show_note_heading"
    assert blocks[0][1]["heading"] == "Support the Show"
    assert blocks[0][1]["icon"] == "support"
    assert blocks[1] == (
        "paragraph",
        '<p>Support us on <a href="https://example.com/support">Patreon</a>.</p>',
    )


def test_support_boilerplate_link_list_renders_as_icon_heading_and_copy() -> None:
    blocks, changed = structured_show_note_detail_blocks(
        "<h3>Support the Show</h3>"
        "<ul>"
        '<li><a href="http://learndjango.com">LearnDjango.com</a></li>'
        '<li><a href="https://btn.dev/">Button</a></li>'
        '<li><a href="https://django-news.com">Django News newsletter</a></li>'
        "</ul>"
    )

    assert changed is True
    assert [name for name, _value in blocks] == ["show_note_link_list"]
    value = blocks[0][1]
    assert value["kind"] == "auto"
    assert value["icon"] == "support"
    assert value["show_items"] is False
    assert "purchasing a book" in value["intro"]
    assert "Django News newsletter" in value["intro"]

    html = render_to_string(
        "cast/django_chat/show_notes/link_list.html",
        {
            "value": _template_value(value),
            "render_for_feed": False,
            "display_kind": value["icon"],
        },
    )
    soup = BeautifulSoup(html, "html.parser")
    assert soup.select_one(".show-note-icon--support") is not None
    assert soup.find("ul") is None
    text = soup.get_text(" ", strip=True)
    for punct in ",.":
        text = text.replace(f" {punct}", punct)
    assert text == (
        "Support the Show This podcast does not have any ads or sponsors. "
        "To support the show, please consider purchasing a book, signing up "
        "for Button, or reading the Django News newsletter."
    )


def test_unheaded_leading_list_with_surrounding_text_stays_source_html() -> None:
    blocks, changed = structured_show_note_detail_blocks(
        "<ul>"
        '<li><a href="https://example.com/talk">Talk</a> - PyCon talk by Example</li>'
        '<li>See <a href="https://example.com/profile">Profile</a></li>'
        '<li><a href="https://example.com/one">One</a> and '
        '<a href="https://example.com/two">Two</a></li>'
        "</ul>"
    )

    assert changed is False
    assert [name for name, _value in blocks] == ["paragraph"]
    assert "PyCon talk by Example" in blocks[0][1]
    assert "See" in blocks[0][1]
    assert ">One</a> and <a" in blocks[0][1]


def test_unheaded_leading_link_only_list_converts_without_visible_links_heading() -> None:
    blocks, changed = structured_show_note_detail_blocks(
        '<ul><li><a href="https://example.com/talk">Talk</a></li></ul>'
    )

    assert changed is True
    html = render_to_string(
        "cast/django_chat/show_notes/link_list.html",
        {
            "value": _template_value(blocks[0][1]),
            "render_for_feed": False,
        },
    )

    assert html.count("Talk") == 1
    assert "Links" not in html
    assert html.count('href="https://example.com/talk"') == 1


def test_unheaded_leading_list_with_linkless_item_stays_source_html() -> None:
    blocks, changed = structured_show_note_detail_blocks(
        "<ul>"
        '<li><a href="https://example.com/one">One</a></li>'
        "<li>Missing link stays legacy.</li>"
        "</ul>"
        "<h3>Support the Show</h3>"
        '<p>Support us on <a href="https://example.com/support">Patreon</a>.</p>'
    )

    # The linkless leading list stays raw; the "Support the Show" heading is
    # offloaded by D5 with its copy preserved as a following paragraph.
    assert changed is True
    assert [name for name, _value in blocks] == ["paragraph", "show_note_heading", "paragraph"]
    assert blocks[0][1] == (
        "<ul>"
        '<li><a href="https://example.com/one">One</a></li>'
        "<li>Missing link stays legacy.</li>"
        "</ul>"
    )
    assert blocks[1][1]["heading"] == "Support the Show"
    assert blocks[1][1]["icon"] == "support"
    assert blocks[2] == (
        "paragraph",
        '<p>Support us on <a href="https://example.com/support">Patreon</a>.</p>',
    )


def test_unheaded_leading_list_with_no_valid_links_stays_unstructured() -> None:
    blocks, changed = structured_show_note_detail_blocks(
        "<ul><li>No link here.</li><li><a>Missing href.</a></li></ul>"
    )

    assert changed is False
    assert blocks == [("paragraph", "<ul><li>No link here.</li><li><a>Missing href.</a></li></ul>")]


def test_raw_markdown_like_notes_convert_to_structured_blocks() -> None:
    blocks, changed = structured_show_note_detail_blocks(
        "* [Michael Herman personal site](https://mherman.org)\n"
        "* [TestDriven.io](https://testdriven.io)\n"
        "\n"
        "#### SHAMELESS PLUGS\n"
        "* William's [books on Django](https://wsvincent.com/books)\n"
        "* Carlton's website [Noumenal](https://noumenal.es/)"
    )

    assert changed is True
    assert [name for name, _value in blocks] == [
        "show_note_link_list",
        "show_note_heading",
        "paragraph",
    ]
    assert blocks[0][1]["show_heading"] is False
    assert [item["title"] for item in blocks[0][1]["items"]] == [
        "Michael Herman personal site",
        "TestDriven.io",
    ]
    # The Shameless Plugs list has prose-prefixed items (non-convertible), so D5
    # offloads the heading with an icon and keeps the list as a raw paragraph.
    assert blocks[1][1]["heading"] == "SHAMELESS PLUGS"
    assert blocks[1][1]["icon"] == "shameless_plugs"
    assert blocks[2][1] == (
        "<ul><li>William's "
        '<a href="https://wsvincent.com/books">books on Django</a></li>'
        '<li>Carlton\'s website <a href="https://noumenal.es/">Noumenal</a></li></ul>'
    )


def test_structure_episode_body_show_notes_reports_repair_classes() -> None:
    body = [
        {
            "type": "detail",
            "value": [
                {
                    "type": "paragraph",
                    "value": (
                        "* [Example](https://example.com)\n"
                        "#### SHAMELESS PLUGS\n"
                        "* [Plug](https://example.com/plug)"
                    ),
                    "id": "detail-paragraph",
                }
            ],
            "id": "detail",
        },
    ]

    structured, report = structure_episode_body_show_notes_with_report(body)
    structured_again, report_again = structure_episode_body_show_notes_with_report(structured)

    assert report.changed is True
    assert report.implicit_link_lists_converted == 1
    assert report.implicit_link_list_headings_hidden == 1
    assert report.implicit_link_lists_skipped == 0
    assert report.raw_markdown_like is True
    assert structured[0]["value"][0]["type"] == "show_note_link_list"
    assert structured[0]["value"][1]["type"] == "show_note_link_list"
    assert report_again.changed is False
    assert report_again.implicit_link_lists_converted == 0
    assert structured_again == structured


def test_no_source_unchanged_detail_does_not_report_action_counters() -> None:
    body = [
        {
            "type": "detail",
            "value": [
                {
                    "type": "paragraph",
                    "value": "<p>Just ordinary prose with no headings or lists.</p>",
                    "id": "prose",
                },
            ],
            "id": "detail",
        },
    ]

    structured, report = structure_episode_body_show_notes_with_report(body)

    assert structured == body
    assert report.changed is False
    assert report.implicit_link_lists_converted == 0
    assert report.implicit_link_list_headings_hidden == 0
    assert report.implicit_link_lists_skipped == 0
    assert report.support_copy_sections_restored == 0


def test_multi_link_sponsor_list_stays_unstructured() -> None:
    html = (
        "<p>Sponsor</p>"
        "<ul>"
        '<li><a href="https://example.com/one">One</a></li>'
        '<li><a href="https://example.com/two">Two</a></li>'
        "</ul>"
    )

    blocks, changed = structured_show_note_detail_blocks(html)

    # A multi-link sponsor list is not convertible to a sponsor block, so D5
    # offloads the heading (with an icon) and keeps the links verbatim.
    assert changed is True
    assert [name for name, _value in blocks] == ["show_note_heading", "paragraph"]
    assert blocks[0][1]["heading"] == "Sponsor"
    assert blocks[0][1]["icon"] == "sponsor"
    assert blocks[1] == (
        "paragraph",
        "<ul>"
        '<li><a href="https://example.com/one">One</a></li>'
        '<li><a href="https://example.com/two">Two</a></li>'
        "</ul>",
    )


def test_structured_show_note_detail_blocks_offload_unsupported_sections() -> None:
    html = (
        "<p>Intro copy stays.</p><h3>Links</h3><ul><li>Missing link stays unstructured.</li></ul>"
    )

    blocks, changed = structured_show_note_detail_blocks(html)

    # D5: the unconvertible Links section becomes an iconed heading block, with
    # the intro and list preserved verbatim around it.
    assert changed is True
    assert [name for name, _value in blocks] == ["paragraph", "show_note_heading", "paragraph"]
    assert blocks[0][1] == "<p>Intro copy stays.</p>"
    assert blocks[1][1]["heading"] == "Links"
    assert blocks[1][1]["icon"] == "links"
    assert blocks[2][1] == "<ul><li>Missing link stays unstructured.</li></ul>"


def test_empty_heading_is_preserved_as_raw_content() -> None:
    # An empty heading must not become a show_note_heading with a blank
    # (required) heading; D5 only offloads headings with non-empty text.
    blocks, changed = structured_show_note_detail_blocks("<h3></h3><p>Copy</p>")

    assert changed is False
    assert blocks == [("paragraph", "<h3></h3><p>Copy</p>")]


def test_empty_heading_between_sections_is_not_offloaded() -> None:
    blocks, changed = structured_show_note_detail_blocks("<h3></h3><p>x</p><h3>Outro</h3><p>y</p>")

    assert [name for name, _value in blocks] == ["paragraph", "show_note_heading", "paragraph"]
    assert blocks[0][1] == "<h3></h3><p>x</p>"
    assert blocks[1][1]["heading"] == "Outro"
    assert blocks[1][1]["icon"] == "default"
    assert blocks[2][1] == "<p>y</p>"


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
    soup = BeautifulSoup(content, "html.parser")
    show_notes = soup.select_one(".show-notes")
    assert show_notes is not None
    assert show_notes.select_one('a[href="https://github.com/RealOrangeOne/django-tasks"]')
    assert "django-tasks and Jake's GitHub" in show_notes.get_text(" ", strip=True)
    headings = [heading.get_text(strip=True) for heading in show_notes.select("h3")]
    assert headings[:7] == [
        "Episode Summary",
        "Episode Notes",
        "🔗 Links",
        "Projects",
        "Books",
        "YouTube",
        "Sponsor",
    ]
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
    assert "<h3>🔗 Links</h3>" in content
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
