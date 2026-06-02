"""Regression tests for the import-pipeline security hardening.

Covers the stored-XSS sanitizer for imported show-note HTML and the
SSRF/local-file-read guards on outbound fetches.
"""

from __future__ import annotations

import pytest

from django_chat.imports.import_sample import _episode_body
from django_chat.imports.show_note_backfill import _sanitize_episode_body
from django_chat.imports.show_notes import (
    _render_inline_markdown,
    sanitize_show_note_html,
    structured_show_note_detail_blocks,
)
from django_chat.imports.source_data import EpisodeSourceData, _safe_link_url
from django_chat.imports.staging_transcripts import extract_podlove_api_url
from django_chat.imports.url_safety import (
    UnsafeURLError,
    _resolve_global_ip,
    safe_urlopen,
    validate_outbound_url,
)


def _bare_episode_source(title: str) -> EpisodeSourceData:
    return EpisodeSourceData(
        matching_key="k",
        title=title,
        published_at=None,
        rss_guid=None,
        simplecast_episode_id=None,
        slug=None,
        episode_number=None,
        rss_enclosure_url=None,
        simplecast_enclosure_url=None,
        rss=None,
        simplecast=None,
    )


class TestSanitizeShowNoteHTML:
    def test_drops_script_tags_with_content(self) -> None:
        result = sanitize_show_note_html("<p>hi</p><script>alert(1)</script>")
        assert "<script" not in result
        assert "alert(1)" not in result
        assert "<p>hi</p>" in result

    def test_strips_event_handler_attributes(self) -> None:
        result = sanitize_show_note_html('<img src="x" onerror="alert(1)">text')
        assert "onerror" not in result
        assert "<img" not in result  # img is not in the allowlist; unwrapped
        assert "text" in result

    def test_strips_javascript_href(self) -> None:
        result = sanitize_show_note_html('<a href="javascript:alert(1)">click</a>')
        assert "javascript:" not in result
        assert "href" not in result
        assert "click" in result

    def test_keeps_safe_link(self) -> None:
        result = sanitize_show_note_html('<a href="https://example.com">x</a>')
        assert 'href="https://example.com"' in result

    def test_keeps_mailto_link(self) -> None:
        result = sanitize_show_note_html('<a href="mailto:hi@example.com">mail</a>')
        assert "mailto:hi@example.com" in result

    def test_drops_iframe(self) -> None:
        result = sanitize_show_note_html('<p>a</p><iframe src="//evil"></iframe>')
        assert "iframe" not in result

    def test_preserves_safe_rel_and_formatting(self) -> None:
        html = '<p>By <a href="https://e.com" rel="noopener noreferrer"><strong>X</strong></a></p>'
        assert sanitize_show_note_html(html) == html

    def test_drops_cdata_parser_differential_payload(self) -> None:
        # html.parser keeps `<![CDATA[ ... ]]>` as one opaque node, hiding the
        # embedded <script> from tag-level checks; a browser treats it as a
        # bogus comment and runs the script. The sanitizer must strip it.
        result = sanitize_show_note_html("<a><![CDATA[</a><script>alert(1)</script>]]>")
        assert "<script" not in result
        assert "CDATA" not in result
        assert "alert(1)" not in result

    def test_drops_html_comments(self) -> None:
        result = sanitize_show_note_html("<p>a</p><!-- <script>x</script> -->")
        assert "<script" not in result
        assert "<!--" not in result

    def test_paragraph_fallback_block_is_sanitized(self) -> None:
        blocks, _ = structured_show_note_detail_blocks(
            "<p>Listen</p><script>alert(document.cookie)</script>"
        )
        assert len(blocks) == 1
        assert blocks[0][0] == "paragraph"
        assert "<script" not in blocks[0][1]


class TestRenderInlineMarkdown:
    def test_drops_javascript_scheme_link(self) -> None:
        result = _render_inline_markdown("[click](javascript:alert(1))")
        assert "javascript:" not in result
        assert "<a" not in result
        assert "click" in result

    def test_keeps_http_link(self) -> None:
        result = _render_inline_markdown("[site](https://example.com)")
        assert '<a href="https://example.com">site</a>' in result


class TestValidateOutboundURL:
    def test_rejects_file_scheme(self) -> None:
        with pytest.raises(UnsafeURLError):
            validate_outbound_url("file:///etc/passwd")

    def test_rejects_metadata_ip(self) -> None:
        with pytest.raises(UnsafeURLError):
            validate_outbound_url("http://169.254.169.254/latest/meta-data/")

    def test_rejects_localhost(self) -> None:
        with pytest.raises(UnsafeURLError):
            validate_outbound_url("http://127.0.0.1:8000/internal")

    def test_rejects_private_ip(self) -> None:
        with pytest.raises(UnsafeURLError):
            validate_outbound_url("http://10.0.0.5/secret")

    def test_rejects_cgnat_ip(self) -> None:
        with pytest.raises(UnsafeURLError):
            validate_outbound_url("http://100.64.0.1/internal")

    def test_accepts_public_https(self) -> None:
        assert (
            validate_outbound_url("https://api.simplecast.com/podcasts")
            == "https://api.simplecast.com/podcasts"
        )


class TestEpisodeBodyTitleFallback:
    def test_malicious_title_fallback_is_sanitized(self) -> None:
        body = _episode_body(_bare_episode_source("<script>alert(1)</script>Hi"))
        overview_html = body[0][1][0][1]
        assert "<script" not in overview_html
        assert "alert(1)" not in overview_html
        assert "Hi" in overview_html


class TestResolveGlobalIP:
    def test_localhost_is_rejected_at_resolution(self) -> None:
        # localhost resolves to 127.0.0.1 (non-global): the connection-time pin
        # raises before any socket is opened, defeating DNS rebinding.
        with pytest.raises(UnsafeURLError):
            _resolve_global_ip("localhost", 80)


class TestSafeURLOpenHTTPS:
    def test_https_fetch_builds_connection_without_typeerror(self) -> None:
        # Regression: http.client.HTTPSConnection (Python >=3.12) rejects a
        # `check_hostname` kwarg, so passing it broke every HTTPS fetch with a
        # TypeError at connection construction. A `.invalid` host fails DNS fast
        # (no network), surfacing the construction step without a real request.
        with pytest.raises(Exception) as exc_info:  # noqa: PT011 - asserting NOT TypeError
            safe_urlopen("https://nonexistent-host.invalid/", timeout=2)
        assert not isinstance(exc_info.value, TypeError)


class TestSanitizeEpisodeBody:
    def test_sanitizes_overview_detail_and_leaves_other_blocks(self) -> None:
        body = [
            {
                "type": "overview",
                "value": [{"type": "paragraph", "value": "<p>ok</p><script>alert(1)</script>"}],
            },
            {
                "type": "detail",
                "value": [
                    {
                        "type": "show_note_link_list",
                        "value": {
                            "heading": "Links",
                            "kind": "links",
                            "intro": "<p>i</p><script>x</script>",
                            "items": [
                                {
                                    "title": "t",
                                    "url": "https://e.com",
                                    "description": "<b>d</b><img src=x onerror=alert(1)>",
                                    "extra_links": [],
                                }
                            ],
                        },
                    },
                    {
                        "type": "show_note_sponsor",
                        "value": {
                            "heading": "Sponsor",
                            "sponsor_name": "S",
                            "sponsor_url": "https://s.com",
                            "copy": "<p>c</p><iframe src=//evil></iframe>",
                            "coupon_code": "",
                        },
                    },
                ],
            },
            {"type": "image", "value": 42},
        ]
        new_body, changed = _sanitize_episode_body(body)
        assert changed
        serialized = str(new_body)
        assert "<script" not in serialized
        assert "onerror" not in serialized
        assert "iframe" not in serialized
        # Non-show-note blocks (image PKs, embeds, …) are left untouched.
        assert new_body[2] == {"type": "image", "value": 42}

    def test_no_change_for_clean_body(self) -> None:
        body = [
            {"type": "overview", "value": [{"type": "paragraph", "value": "<p>clean</p>"}]},
        ]
        _new_body, changed = _sanitize_episode_body(body)
        assert not changed


@pytest.mark.django_db
class TestSanitizeImportedEpisodeBodies:
    def test_scoped_to_imported_episodes(self) -> None:
        from cast.models import Episode

        from django_chat.imports.import_sample import import_django_chat_sample
        from django_chat.imports.models import EpisodeSourceMetadata
        from django_chat.imports.show_note_backfill import sanitize_imported_episode_bodies

        result = import_django_chat_sample()
        scanned, _changed = sanitize_imported_episode_bodies(
            Episode=Episode,
            EpisodeSourceMetadata=EpisodeSourceMetadata,
            write=True,
        )
        # Only episodes that have import metadata are scanned — manually
        # authored episodes (no metadata) are never touched.
        assert scanned == EpisodeSourceMetadata.objects.count()
        assert scanned == len(result.episode_metadata)

    def test_manual_episode_body_is_left_unchanged(self) -> None:
        from cast.models import Episode
        from django.utils import timezone

        from django_chat.imports.import_sample import import_django_chat_sample
        from django_chat.imports.models import EpisodeSourceMetadata
        from django_chat.imports.show_note_backfill import sanitize_imported_episode_bodies

        result = import_django_chat_sample()
        # A manually authored episode (no EpisodeSourceMetadata) whose editor
        # rich text holds a Wagtail internal link — the sanitizer would strip
        # `linktype`/`id`, so the scoped backfill must not touch it.
        manual_html = '<p>See <a linktype="page" id="1">About</a></p>'
        manual = Episode(
            title="Manual Episode",
            slug="manual-internal-link-episode",
            visible_date=timezone.now(),
            body=[("overview", [("paragraph", manual_html)])],
        )
        result.podcast.add_child(instance=manual)

        sanitize_imported_episode_bodies(
            Episode=Episode,
            EpisodeSourceMetadata=EpisodeSourceMetadata,
            write=True,
        )

        # Inspect the unrendered StreamField data (raw_data), not the rendered
        # HTML, so the assertion sees the stored markup as-is.
        manual.refresh_from_db()
        stored = str(getattr(manual.body, "raw_data", manual.body))
        assert 'linktype="page"' in stored
        assert 'id="1"' in stored


@pytest.mark.django_db
class TestDropUnsafeSourceLinks:
    def test_removes_unsafe_link_rows_and_keeps_safe_ones(self) -> None:
        from django_chat.imports.import_sample import import_django_chat_sample
        from django_chat.imports.models import PodcastSourceLink
        from django_chat.imports.show_note_backfill import drop_unsafe_source_links

        result = import_django_chat_sample()
        metadata = result.podcast_metadata
        safe = PodcastSourceLink.objects.create(
            podcast_metadata=metadata,
            source_key="safe",
            source="test",
            location="menu",
            name="Safe",
            url="https://example.com/safe",
        )
        unsafe = PodcastSourceLink.objects.create(
            podcast_metadata=metadata,
            source_key="unsafe",
            source="test",
            location="menu",
            name="Unsafe",
            url="javascript:alert(document.cookie)",
        )

        scanned, removed = drop_unsafe_source_links(PodcastSourceLink=PodcastSourceLink, write=True)

        assert scanned >= 2
        assert removed >= 1
        assert PodcastSourceLink.objects.filter(pk=safe.pk).exists()
        assert not PodcastSourceLink.objects.filter(pk=unsafe.pk).exists()


class TestSafeLinkURL:
    def test_rejects_javascript_scheme(self) -> None:
        assert _safe_link_url("javascript:alert(document.cookie)") is None

    def test_rejects_data_scheme(self) -> None:
        assert _safe_link_url("data:text/html,<script>alert(1)</script>") is None

    def test_rejects_scheme_relative(self) -> None:
        assert _safe_link_url("//evil.example") is None

    def test_accepts_https(self) -> None:
        assert _safe_link_url(" https://example.com/x ") == "https://example.com/x"

    def test_accepts_mailto(self) -> None:
        assert _safe_link_url("mailto:hi@example.com") == "mailto:hi@example.com"


class TestExtractPodloveAPIURL:
    def test_same_host_relative_url_is_accepted(self) -> None:
        html = '<podlove-player data-url="/api/audios/podlove/1/"></podlove-player>'
        result = extract_podlove_api_url(html, base_url="https://staging.example.test/episodes/x/")
        assert result == "https://staging.example.test/api/audios/podlove/1/"

    def test_file_scheme_data_url_is_rejected(self) -> None:
        html = '<podlove-player data-url="file:///etc/passwd"></podlove-player>'
        with pytest.raises(ValueError, match="not on the expected staging host"):
            extract_podlove_api_url(html, base_url="https://staging.example.test/episodes/x/")

    def test_cross_host_data_url_is_rejected(self) -> None:
        html = '<podlove-player data-url="http://169.254.169.254/meta"></podlove-player>'
        with pytest.raises(ValueError, match="not on the expected staging host"):
            extract_podlove_api_url(html, base_url="https://staging.example.test/episodes/x/")
