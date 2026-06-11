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

        call_command("seed_django_chat_diarized_demo")

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

        call_command("seed_django_chat_diarized_demo")
        name_after_first = Audio.objects.get(pk=episode.podcast_audio.pk).transcript.podlove.name

        call_command("seed_django_chat_diarized_demo")
        name_after_second = Audio.objects.get(pk=episode.podcast_audio.pk).transcript.podlove.name

        # Same file path (no uniqueness-suffix orphan) and no duplicate contributors.
        assert name_after_first == name_after_second
        episode_contributor_model = apps.get_model("cast", "EpisodeContributor")
        assert episode_contributor_model.objects.filter(episode=episode).count() == 3
