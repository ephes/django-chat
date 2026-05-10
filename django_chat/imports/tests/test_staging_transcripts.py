from __future__ import annotations

import json
from typing import Any

import pytest
from cast.models import Episode
from django.apps import apps
from django.test import override_settings

from django_chat.imports.import_sample import DownloadedAudio, import_django_chat_sample
from django_chat.imports.staging_transcripts import (
    extract_podlove_api_url,
    import_staging_transcripts,
    podlove_segments_to_dote,
    podlove_segments_to_vtt,
)


def test_extract_podlove_api_url_resolves_staging_relative_url() -> None:
    html = '<podlove-player data-url="/api/audios/podlove/1/post/4/"></podlove-player>'

    url = extract_podlove_api_url(
        html,
        base_url="https://djangochat.staging.django-cast.com/episodes/example/",
    )

    assert url == "https://djangochat.staging.django-cast.com/api/audios/podlove/1/post/4/"


def test_podlove_segments_are_rendered_as_feed_transcript_formats() -> None:
    segment = _podlove_segment()

    assert podlove_segments_to_vtt([segment]) == (
        "WEBVTT\n\n"
        "00:00:00.000 --> 00:00:02.000\n"
        "Generated transcript segment for an imported episode.\n\n"
    )
    assert podlove_segments_to_dote([segment]) == {
        "lines": [
            {
                "startTime": "00:00:00,000",
                "endTime": "00:00:02,000",
                "speakerDesignation": "Host",
                "text": "Generated transcript segment for an imported episode.",
            }
        ]
    }


@pytest.mark.django_db
def test_import_staging_transcripts_attaches_cast_transcript_files(tmp_path: Any) -> None:
    fetcher = FakeStagingFetcher()

    with override_settings(MEDIA_ROOT=tmp_path):
        import_django_chat_sample(copy_audio=True, audio_downloader=FakeAudioDownloader())
        result = import_staging_transcripts(
            host="https://staging.example.test",
            slugs=["django-tasks-jake-howard"],
            text_fetcher=fetcher,
        )

        episode = Episode.objects.get(slug="django-tasks-jake-howard")
        transcript = apps.get_model("cast", "Transcript").objects.get(audio=episode.podcast_audio)
        podlove_data = transcript.podlove_data
        dote_data = transcript.dote_data
        vtt = transcript.vtt.open("r").read()

    assert result.imported_count == 1
    assert result.skipped_count == 0
    assert fetcher.urls == [
        "https://staging.example.test/episodes/django-tasks-jake-howard/",
        "https://staging.example.test/api/audios/podlove/1/post/4/",
    ]
    assert podlove_data["transcripts"] == [_podlove_segment()]
    assert dote_data["lines"][0]["speakerDesignation"] == "Host"
    assert "Generated transcript segment for an imported episode." in vtt


@pytest.mark.django_db
def test_import_staging_transcripts_uses_overridden_default_podcast_slug(tmp_path: Any) -> None:
    fetcher = FakeStagingFetcher()

    with override_settings(MEDIA_ROOT=tmp_path, DJANGO_CHAT_PODCAST_SLUG="custom-episodes"):
        import_django_chat_sample(copy_audio=True, audio_downloader=FakeAudioDownloader())
        result = import_staging_transcripts(
            host="https://staging.example.test",
            slugs=["django-tasks-jake-howard"],
            text_fetcher=fetcher,
        )

    assert result.imported_count == 1
    assert (
        fetcher.urls[0] == "https://staging.example.test/custom-episodes/django-tasks-jake-howard/"
    )


@pytest.mark.django_db
def test_import_staging_transcripts_replaces_existing_files(tmp_path: Any) -> None:
    fetcher = FakeStagingFetcher()

    with override_settings(MEDIA_ROOT=tmp_path):
        import_django_chat_sample(copy_audio=True, audio_downloader=FakeAudioDownloader())
        first = import_staging_transcripts(
            host="https://staging.example.test",
            slugs=["django-tasks-jake-howard"],
            text_fetcher=fetcher,
        )
        second = import_staging_transcripts(
            host="https://staging.example.test",
            slugs=["django-tasks-jake-howard"],
            text_fetcher=fetcher,
        )
        transcript_dir = tmp_path / "cast_transcript" / "django-chat-staging"
        transcript_files = sorted(path.name for path in transcript_dir.iterdir())

    assert first.imported_count == 1
    assert second.imported_count == 1
    assert transcript_files == [
        "django-tasks-jake-howard.dote.json",
        "django-tasks-jake-howard.podlove.json",
        "django-tasks-jake-howard.vtt",
    ]


@pytest.mark.django_db
def test_import_staging_transcripts_reports_missing_slug_reasons() -> None:
    import_django_chat_sample()

    result = import_staging_transcripts(
        host="https://staging.example.test",
        slugs=["django-tasks-jake-howard", "missing-slug"],
        text_fetcher=FakeStagingFetcher(),
    )

    assert [(item.slug, item.reason) for item in result.items] == [
        ("django-tasks-jake-howard", "local episode has no copied audio"),
        ("missing-slug", "local episode not found"),
    ]


class FakeAudioDownloader:
    def __call__(self, source_url: str) -> DownloadedAudio:
        return DownloadedAudio(
            content=f"fake audio bytes for {source_url}".encode(),
            content_type="audio/mpeg",
            content_length=123,
            filename="sample.mp3",
        )


class FakeStagingFetcher:
    def __init__(self) -> None:
        self.urls: list[str] = []

    def __call__(self, url: str, _timeout: float) -> str:
        self.urls.append(url)
        if url.endswith("/django-tasks-jake-howard/"):
            return '<podlove-player data-url="/api/audios/podlove/1/post/4/"></podlove-player>'
        if url.endswith("/api/audios/podlove/1/post/4/"):
            return json.dumps({"transcripts": [_podlove_segment()]})
        msg = f"unexpected URL: {url}"
        raise AssertionError(msg)


def _podlove_segment() -> dict[str, Any]:
    return {
        "start": "00:00:00.000",
        "start_ms": 0,
        "end": "00:00:02.000",
        "end_ms": 2000,
        "speaker": "Host",
        "voice": "",
        "text": "Generated transcript segment for an imported episode.",
    }
