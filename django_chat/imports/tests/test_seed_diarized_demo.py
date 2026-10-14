"""Tests for the reproducible diarized-transcript demo seed command."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from cast.models import Audio, Episode
from django.apps import apps
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.test import Client, override_settings
from django.urls import reverse

from django_chat.imports.import_sample import DownloadedAudio, import_django_chat_sample

DEMO_SPEAKERS = {"Will Vincent", "Carlton Gibson", "Jake Howard"}


class _FakeAudioDownloader:
    def __call__(self, source_url: str) -> DownloadedAudio:
        content = b"fake audio bytes"
        return DownloadedAudio(
            content=content,
            content_type="audio/mpeg",
            content_length=len(content),
            filename="sample.mp3",
        )


def _attach_plain_transcript(audio: Audio, segments: int = 12) -> Any:
    """Attach a transcript with no per-cue speaker labels (the imported state)."""
    transcript_model = apps.get_model("cast", "Transcript")
    transcript = transcript_model.objects.create(audio=audio)
    podlove = {
        "transcripts": [
            {
                "start_ms": index * 2_000,
                "end_ms": (index + 1) * 2_000,
                "text": f"Imported transcript line {index + 1}.",
            }
            for index in range(segments)
        ]
    }
    transcript.podlove.save("plain.podlove.json", ContentFile(json.dumps(podlove)))
    return transcript


@pytest.mark.django_db
def test_seed_labels_cues_and_assigns_visible_contributors(tmp_path: Path) -> None:
    with override_settings(MEDIA_ROOT=tmp_path):
        import_django_chat_sample(copy_audio=True, audio_downloader=_FakeAudioDownloader())
        episode = Episode.objects.get(slug="django-tasks-jake-howard")
        assert episode.podcast_audio is not None
        _attach_plain_transcript(episode.podcast_audio)

        call_command("seed_django_chat_diarized_demo", allow_non_debug=True)

        episode_contributor_model = apps.get_model("cast", "EpisodeContributor")
        assignments = episode_contributor_model.objects.filter(episode=episode)
        assert sorted(a.contributor.display_name for a in assignments) == [
            "Carlton Gibson",
            "Jake Howard",
            "Will Vincent",
        ]
        assert all(a.contributor.visible for a in assignments)

        with Audio.objects.get(pk=episode.podcast_audio.pk).transcript.podlove.open("r") as handle:
            data = json.load(handle)
        segments = data["transcripts"]
        assert all(segment.get("speaker") for segment in segments)  # every cue labelled
        assert {segment["speaker"] for segment in segments} <= DEMO_SPEAKERS

        # End-to-end: the public player endpoint returns the seeded speaker labels
        # (they survive sanitization because the contributors are visible).
        response = Client().get(
            reverse("cast:api:audio_player_transcript", kwargs={"pk": episode.podcast_audio.pk}),
            {"post_id": episode.pk},
        )
        assert response.status_code == 200
        endpoint_speakers = {cue["speaker"] for cue in response.json()["cues"] if cue["speaker"]}
        assert endpoint_speakers and endpoint_speakers <= DEMO_SPEAKERS


@pytest.mark.django_db
def test_seed_is_idempotent(tmp_path: Path) -> None:
    with override_settings(MEDIA_ROOT=tmp_path):
        import_django_chat_sample(copy_audio=True, audio_downloader=_FakeAudioDownloader())
        episode = Episode.objects.get(slug="django-tasks-jake-howard")
        _attach_plain_transcript(episode.podcast_audio)

        call_command("seed_django_chat_diarized_demo", allow_non_debug=True)
        first = Audio.objects.get(pk=episode.podcast_audio.pk).transcript.podlove
        with first.open("r") as handle:
            data_after_first = json.load(handle)

        call_command("seed_django_chat_diarized_demo", allow_non_debug=True)
        second = Audio.objects.get(pk=episode.podcast_audio.pk).transcript.podlove
        with second.open("r") as handle:
            data_after_second = json.load(handle)

        # Same labels, the transcript points at an existing file, the previous
        # file was removed after the swap (no orphan), and no duplicate contributors.
        assert data_after_first == data_after_second
        assert second.storage.exists(second.name)
        if first.name != second.name:
            assert not first.storage.exists(first.name)
        podlove_files = [path for path in tmp_path.rglob("*.json") if path.is_file()]
        assert len(podlove_files) == 1
        episode_contributor_model = apps.get_model("cast", "EpisodeContributor")
        assert episode_contributor_model.objects.filter(episode=episode).count() == 3


@pytest.mark.django_db
def test_seed_refuses_without_debug_or_flag(tmp_path: Path) -> None:
    from django.core.management.base import CommandError

    with override_settings(MEDIA_ROOT=tmp_path, DEBUG=False):
        import_django_chat_sample(copy_audio=True, audio_downloader=_FakeAudioDownloader())
        episode = Episode.objects.get(slug="django-tasks-jake-howard")
        transcript = _attach_plain_transcript(episode.podcast_audio)
        with transcript.podlove.open("r") as handle:
            before = handle.read()

        with pytest.raises(CommandError, match="DEBUG"):
            call_command("seed_django_chat_diarized_demo")

        transcript.refresh_from_db()
        with transcript.podlove.open("r") as handle:
            assert handle.read() == before


@pytest.mark.django_db
def test_seed_runs_when_debug_is_on(tmp_path: Path) -> None:
    with override_settings(MEDIA_ROOT=tmp_path, DEBUG=True):
        import_django_chat_sample(copy_audio=True, audio_downloader=_FakeAudioDownloader())
        episode = Episode.objects.get(slug="django-tasks-jake-howard")
        _attach_plain_transcript(episode.podcast_audio)

        call_command("seed_django_chat_diarized_demo")

        transcript = Audio.objects.get(pk=episode.podcast_audio.pk).transcript
        with transcript.podlove.open("r") as handle:
            assert all(segment.get("speaker") for segment in json.load(handle)["transcripts"])


@pytest.mark.django_db
def test_seed_keeps_original_transcript_when_write_fails(tmp_path: Path, monkeypatch) -> None:
    with override_settings(MEDIA_ROOT=tmp_path):
        import_django_chat_sample(copy_audio=True, audio_downloader=_FakeAudioDownloader())
        episode = Episode.objects.get(slug="django-tasks-jake-howard")
        transcript = _attach_plain_transcript(episode.podcast_audio)
        original_name = transcript.podlove.name
        storage = transcript.podlove.storage

        def failing_save(*args: Any, **kwargs: Any) -> str:
            raise OSError("disk full")

        monkeypatch.setattr(storage, "save", failing_save)
        with pytest.raises(OSError, match="disk full"):
            call_command("seed_django_chat_diarized_demo", allow_non_debug=True)
        monkeypatch.undo()

        transcript.refresh_from_db()
        assert transcript.podlove.name == original_name
        assert storage.exists(original_name)


@pytest.mark.django_db
def test_seed_reruns_keep_transcript_name_within_field_length(tmp_path: Path) -> None:
    with override_settings(MEDIA_ROOT=tmp_path):
        import_django_chat_sample(copy_audio=True, audio_downloader=_FakeAudioDownloader())
        episode = Episode.objects.get(slug="django-tasks-jake-howard")
        transcript = _attach_plain_transcript(episode.podcast_audio)
        max_length = transcript._meta.get_field("podlove").max_length

        for _ in range(12):
            call_command("seed_django_chat_diarized_demo", allow_non_debug=True)

        transcript.refresh_from_db()
        assert len(transcript.podlove.name) <= max_length
        assert transcript.podlove.storage.exists(transcript.podlove.name)
