from __future__ import annotations

from io import StringIO
from pathlib import Path

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings

from django_chat.imports.feed_smoke import (
    compare_django_chat_sample_feed,
    compare_source_to_generated_feed,
    format_feed_smoke_result,
    load_source_feed,
    parse_generated_podcast_feed,
)
from django_chat.imports.import_sample import DownloadedAudio, import_django_chat_sample
from django_chat.imports.models import EpisodeAudioImportMetadata, EpisodeSourceMetadata


def test_generated_feed_parser_reads_smoke_fields() -> None:
    generated = parse_generated_podcast_feed(
        b"""<?xml version="1.0"?>
        <rss xmlns:atom="http://www.w3.org/2005/Atom"
             xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"
             version="2.0">
          <channel>
            <atom:link href="http://testserver/episodes/feed/podcast/mp3/rss.xml"
                       rel="self" />
            <title>Django Chat</title>
            <link>http://testserver/episodes/</link>
            <item>
              <guid isPermaLink="false">2c78bb02-8162-44f0-b22d-a188f5bbdb9e</guid>
              <title>Django Tasks - Jake Howard</title>
              <pubDate>Wed, 15 Apr 2026 08:00:00 +0000</pubDate>
              <enclosure url="/media/sample.mp3" type="audio/mpeg" length="123" />
              <itunes:duration>01:17:43</itunes:duration>
            </item>
          </channel>
        </rss>"""
    )

    assert generated.title == "Django Chat"
    assert generated.link == "http://testserver/episodes/"
    assert generated.self_url == "http://testserver/episodes/feed/podcast/mp3/rss.xml"
    assert len(generated.items) == 1
    item = generated.items[0]
    assert item.guid == "2c78bb02-8162-44f0-b22d-a188f5bbdb9e"
    assert item.published_at is not None
    assert item.published_at.isoformat() == "2026-04-15T08:00:00+00:00"
    assert item.duration_seconds == 4663
    assert item.enclosure is not None
    assert item.enclosure.length == 123


@pytest.mark.django_db
def test_feed_smoke_passes_for_copied_audio_and_reports_known_warnings(
    tmp_path: Path,
) -> None:
    with override_settings(MEDIA_ROOT=tmp_path):
        import_django_chat_sample(copy_audio=True, audio_downloader=FakeAudioDownloader())
        result = compare_django_chat_sample_feed(host="testserver")

    assert result.passed is True
    assert result.source_item_count == 8
    assert result.generated_item_count == 8
    assert result.failures == ()
    warning_text = "\n".join(message.text for message in result.warnings)
    assert "Generated enclosure URLs differ from the Simplecast fixture" in warning_text
    assert "Strict length checking uses copied bytes" in warning_text


@pytest.mark.django_db
def test_feed_smoke_reports_metadata_only_import_as_actionable_failure() -> None:
    import_django_chat_sample()

    result = compare_django_chat_sample_feed(host="testserver")

    assert result.passed is False
    failure_text = "\n".join(message.text for message in result.failures)
    assert "Generated feed item count mismatch: source=8, generated=0" in failure_text
    assert "import_django_chat_sample --copy-audio" in failure_text


@pytest.mark.django_db
def test_feed_smoke_reports_missing_podcast_route_as_actionable_failure() -> None:
    result = compare_django_chat_sample_feed(host="testserver")

    assert result.passed is False
    failure_text = "\n".join(message.text for message in result.failures)
    assert "Generated feed returned HTTP 404" in failure_text
    assert "just manage migrate" in failure_text
    assert "just manage import_django_chat_sample --copy-audio" in failure_text


@pytest.mark.django_db
def test_feed_smoke_fails_on_item_title_mismatch(tmp_path: Path) -> None:
    with override_settings(MEDIA_ROOT=tmp_path):
        import_django_chat_sample(copy_audio=True, audio_downloader=FakeAudioDownloader())
        metadata = EpisodeSourceMetadata.objects.get(episode_number=200)
        episode = metadata.episode
        episode.title = "Changed Local Title"
        episode.save()

        result = compare_django_chat_sample_feed(host="testserver")

    assert result.passed is False
    failure_text = "\n".join(message.text for message in result.failures)
    assert "title mismatch" in failure_text
    assert "Changed Local Title" in failure_text


@pytest.mark.django_db
def test_feed_smoke_fails_when_generated_length_does_not_match_copied_bytes(
    tmp_path: Path,
) -> None:
    with override_settings(MEDIA_ROOT=tmp_path):
        import_django_chat_sample(copy_audio=True, audio_downloader=FakeAudioDownloader())
        audio_metadata = EpisodeAudioImportMetadata.objects.select_related(
            "episode_metadata",
            "audio",
        ).get(episode_metadata__episode_number=200)
        audio = audio_metadata.audio
        audio.data["size"]["mp3"] = 999999
        audio.save(duration=False, cache_file_sizes=False)

        result = compare_django_chat_sample_feed(host="testserver")

    assert result.passed is False
    failure_text = "\n".join(message.text for message in result.failures)
    assert "enclosure copied length mismatch" in failure_text
    assert "copied=" in failure_text
    assert "generated=999999" in failure_text


@pytest.mark.django_db
def test_feed_smoke_management_command_passes_for_copied_audio(tmp_path: Path) -> None:
    with override_settings(MEDIA_ROOT=tmp_path):
        import_django_chat_sample(copy_audio=True, audio_downloader=FakeAudioDownloader())
        stdout = StringIO()
        call_command("compare_django_chat_sample_feed", "--host=testserver", stdout=stdout)

    output = stdout.getvalue()
    assert "PASS strict feed smoke checks passed." in output
    assert "WARN Generated enclosure URLs differ" in output


@pytest.mark.django_db
def test_feed_smoke_management_command_fails_nonzero_for_metadata_only_import() -> None:
    import_django_chat_sample()
    stdout = StringIO()

    with pytest.raises(CommandError, match="feed smoke check failed"):
        call_command("compare_django_chat_sample_feed", "--host=testserver", stdout=stdout)

    output = stdout.getvalue()
    assert "FAIL strict feed smoke checks found" in output
    assert "Generated feed has no items" in output


def test_feed_smoke_format_includes_counts_for_failures() -> None:
    source = load_source_feed()
    generated = parse_generated_podcast_feed(
        b"""<?xml version="1.0"?>
        <rss version="2.0">
          <channel>
            <title>Not Django Chat</title>
            <link>http://testserver/episodes/</link>
          </channel>
        </rss>"""
    )

    result = compare_source_to_generated_feed(
        source,
        generated,
        generated_feed_path="/episodes/feed/podcast/mp3/rss.xml",
        copied_byte_sizes_by_guid={},
    )
    output = format_feed_smoke_result(result)

    assert result.passed is False
    assert "source=8, generated=0" in output
    assert "feed title mismatch" in output


class FakeAudioDownloader:
    def __call__(self, source_url: str) -> DownloadedAudio:
        return DownloadedAudio(
            content=_fake_audio_content(source_url),
            content_type="audio/mpeg",
            content_length=len(_fake_audio_content(source_url)),
            filename="sample.mp3",
        )


def _fake_audio_content(source_url: str) -> bytes:
    return f"fake audio bytes for {source_url}".encode()
