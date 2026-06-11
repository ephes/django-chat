from __future__ import annotations

import json
from typing import Any

import pytest
from cast.models import Episode
from django.apps import apps
from django.core.files.base import ContentFile
from django.test import override_settings

from django_chat.imports.import_sample import DownloadedAudio, import_django_chat_sample
from django_chat.imports.staging_transcripts import (
    _delete_replacement_files,
    _replace_file,
    extract_podlove_api_url,
    import_staging_transcript_for_episode,
    import_staging_transcripts,
    podlove_segments_to_dote,
    podlove_segments_to_vtt,
)


def test_extract_podlove_api_url_reads_custom_player_payload() -> None:
    html = _custom_player_html(audio_id=1, post_id=4)

    url = extract_podlove_api_url(
        html,
        base_url="https://djangochat.staging.django-cast.com/episodes/example/",
    )

    assert url == "https://djangochat.staging.django-cast.com/api/audios/podlove/1/post/4/"


def test_extract_podlove_api_url_reports_missing_transcript() -> None:
    html = _custom_player_html(audio_id=1, post_id=4, with_transcript=False)

    with pytest.raises(ValueError, match="exposes no transcript"):
        extract_podlove_api_url(
            html,
            base_url="https://djangochat.staging.django-cast.com/episodes/example/",
        )


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
    assert len(transcript_files) == 3
    assert sum(name.endswith(".dote.json") for name in transcript_files) == 1
    assert sum(name.endswith(".podlove.json") for name in transcript_files) == 1
    assert sum(name.endswith(".vtt") for name in transcript_files) == 1
    assert all(name.startswith("django-tasks-jake-howard-") for name in transcript_files)


def test_replace_file_keeps_old_file_until_replacement_cleanup() -> None:
    storage = FakeStorage()
    field = FakeField(storage, "old-transcript.json")

    replacement = _replace_file(field, "new-transcript.json", ContentFile("new transcript"))

    assert field.name.startswith("new-transcript-")
    assert field.name.endswith(".json")
    assert storage.events == [("save", field.name)]
    assert replacement is not None
    assert replacement.old_name == "old-transcript.json"
    assert replacement.new_name == field.name

    _delete_replacement_files([replacement], use_new=False)

    assert storage.events == [("save", field.name), ("delete", "old-transcript.json")]


def test_replace_file_does_not_delete_old_file_when_replacement_write_fails() -> None:
    storage = FakeStorage()
    field = FakeField(storage, "old-transcript.json", fail_save=True)

    with pytest.raises(OSError, match="replacement write failed"):
        _replace_file(field, "new-transcript.json", ContentFile("new transcript"))

    assert field.name == "old-transcript.json"
    assert len(storage.events) == 1
    assert storage.events[0][0] == "save"
    assert storage.events[0][1].startswith("new-transcript-")


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


@pytest.mark.django_db
def test_import_staging_transcript_for_episode_reports_missing_audio() -> None:
    import_django_chat_sample()
    episode = Episode.objects.get(slug="django-tasks-jake-howard")
    fetcher = FakeStagingFetcher()

    result = import_staging_transcript_for_episode(
        episode,
        host="https://staging.example.test",
        text_fetcher=fetcher,
    )

    assert result.imported is False
    assert result.segment_count == 0
    assert result.reason == "local episode has no copied audio"
    assert fetcher.urls == []


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
            return _custom_player_html(audio_id=1, post_id=4)
        if url.endswith("/api/audios/podlove/1/post/4/"):
            return json.dumps({"transcripts": [_podlove_segment()]})
        msg = f"unexpected URL: {url}"
        raise AssertionError(msg)


class FakeStorage:
    def __init__(self) -> None:
        self.events: list[tuple[str, str]] = []

    def delete(self, name: str) -> None:
        self.events.append(("delete", name))


class FakeField:
    def __init__(self, storage: FakeStorage, name: str, *, fail_save: bool = False) -> None:
        self.storage = storage
        self.name = name
        self.fail_save = fail_save

    def save(self, name: str, _content: ContentFile, *, save: bool) -> None:
        saved_name = name.rsplit(".", 1)[0] if self.fail_save else name
        self.storage.events.append(("save", saved_name))
        if self.fail_save:
            raise OSError("replacement write failed")
        self.name = saved_name


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


def _custom_player_html(
    *,
    audio_id: int,
    post_id: int,
    with_transcript: bool = True,
    host: str = "https://staging.example.test",
) -> str:
    """Episode-page markup shaped like django-cast's custom player output."""
    payload: dict[str, Any] = {
        "audioId": audio_id,
        "title": "Example Episode",
        "sources": [{"type": "audio/mpeg", "src": f"{host}/media/example.mp3"}],
    }
    if with_transcript:
        payload["transcript"] = {
            "url": f"{host}/api/audios/{audio_id}/player-transcript/?post_id={post_id}"
        }
    payload_json = json.dumps(payload)
    return (
        f'<script id="cast-player-data-{post_id}" type="application/json">'
        f"{payload_json}</script>"
        f'<cast-audio-player id="cast-player-{post_id}" '
        f'data-payload="cast-player-data-{post_id}" data-share="none"></cast-audio-player>'
    )
