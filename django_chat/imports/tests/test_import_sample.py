from __future__ import annotations

from typing import Any, cast

import pytest
from cast.models import Audio, Episode, Podcast
from django.apps import apps
from django.core.management import call_command

from django_chat.imports.import_sample import import_django_chat_sample, load_sample_source_data
from django_chat.imports.models import EpisodeSourceMetadata, PodcastSourceMetadata
from django_chat.imports.source_data import (
    RSS_FEED_URL,
    SIMPLECAST_PODCAST_ID,
    SIMPLECAST_PODCAST_URL,
)


def test_sample_source_matching_keys_are_stable() -> None:
    first_load = load_sample_source_data()
    second_load = load_sample_source_data()

    first_keys = tuple(episode.matching_key for episode in first_load.episodes)
    second_keys = tuple(episode.matching_key for episode in second_load.episodes)

    assert first_keys == second_keys
    assert len(set(first_keys)) == len(first_keys)
    assert "guid:2c78bb02-8162-44f0-b22d-a188f5bbdb9e" in first_keys


@pytest.mark.django_db
def test_sample_import_creates_podcast_episode_pages_and_source_metadata() -> None:
    result = import_django_chat_sample()

    assert result.podcast_created is True
    assert result.episodes_created == 8
    assert len(result.episodes) == 8
    assert len(result.episode_metadata) == 8
    assert Podcast.objects.count() == 1
    assert Episode.objects.count() == 8
    assert PodcastSourceMetadata.objects.count() == 1
    assert EpisodeSourceMetadata.objects.count() == 8

    podcast = Podcast.objects.get()
    assert podcast.title == "Django Chat"
    assert podcast.slug == "episodes"
    assert podcast.author == "William Vincent and Carlton Gibson"
    assert podcast.email == "will@wsvincent.com"
    assert podcast.comments_enabled is False

    podcast_metadata = PodcastSourceMetadata.objects.get()
    assert podcast_metadata.podcast == podcast
    assert podcast_metadata.simplecast_podcast_id == SIMPLECAST_PODCAST_ID
    assert podcast_metadata.rss_feed_url == RSS_FEED_URL
    assert podcast_metadata.simplecast_source_url == SIMPLECAST_PODCAST_URL
    assert podcast_metadata.website_url == "https://djangochat.com"
    assert podcast_metadata.source_is_explicit is False

    latest_metadata = EpisodeSourceMetadata.objects.get(episode_number=200)
    assert latest_metadata.episode.title == "Django Tasks - Jake Howard"
    assert latest_metadata.rss_guid == "2c78bb02-8162-44f0-b22d-a188f5bbdb9e"
    assert latest_metadata.simplecast_episode_id == "af752038-3231-412e-801d-c8cc3cdd90cb"
    assert latest_metadata.simplecast_slug == "django-tasks-jake-howard"
    assert latest_metadata.matching_key == "guid:2c78bb02-8162-44f0-b22d-a188f5bbdb9e"
    assert latest_metadata.rss_source_url == RSS_FEED_URL
    assert latest_metadata.simplecast_source_url.startswith("https://api.simplecast.com/episodes/")
    assert latest_metadata.original_rss_enclosure_url.endswith("?aid=rss_feed&feed=WpQaX_cs")
    assert latest_metadata.simplecast_enclosure_url.startswith(
        "https://dts.podtrac.com/redirect.mp3/"
    )
    assert not latest_metadata.simplecast_enclosure_url.endswith("?aid=rss_feed&feed=WpQaX_cs")
    assert latest_metadata.simplecast_audio_file_url.startswith("https://cdn.simplecast.com/")
    assert latest_metadata.duration_seconds == 4663
    assert latest_metadata.audio_file_size == 74615234
    assert latest_metadata.rss_is_explicit is False
    assert latest_metadata.simplecast_is_explicit is False
    assert "Django-Mantle" in latest_metadata.simplecast_long_description_html
    assert latest_metadata.simplecast_transcript_html.startswith("<p>")
    assert "Jake Howard" in latest_metadata.simplecast_transcript_html
    assert latest_metadata.episode.podcast_audio is None
    assert latest_metadata.episode.comments_enabled is False
    assert Audio.objects.count() == 0
    assert _transcript_count() == 0


@pytest.mark.django_db
def test_sample_import_is_idempotent_on_second_run() -> None:
    first_result = import_django_chat_sample()
    podcast_ids = set(Podcast.objects.values_list("id", flat=True))
    episode_ids = set(Episode.objects.values_list("id", flat=True))
    podcast_metadata_ids = set(PodcastSourceMetadata.objects.values_list("id", flat=True))
    episode_metadata_ids = set(EpisodeSourceMetadata.objects.values_list("id", flat=True))

    second_result = import_django_chat_sample()

    assert first_result.podcast_created is True
    assert first_result.episodes_created == 8
    assert second_result.podcast_created is False
    assert second_result.episodes_created == 0
    assert set(Podcast.objects.values_list("id", flat=True)) == podcast_ids
    assert set(Episode.objects.values_list("id", flat=True)) == episode_ids
    assert set(PodcastSourceMetadata.objects.values_list("id", flat=True)) == podcast_metadata_ids
    assert set(EpisodeSourceMetadata.objects.values_list("id", flat=True)) == episode_metadata_ids
    assert Podcast.objects.count() == 1
    assert Episode.objects.count() == 8
    assert PodcastSourceMetadata.objects.count() == 1
    assert EpisodeSourceMetadata.objects.count() == 8
    assert Audio.objects.count() == 0
    assert _transcript_count() == 0


@pytest.mark.django_db
def test_import_sample_management_command_uses_local_fixtures() -> None:
    call_command("import_django_chat_sample", verbosity=0)

    assert PodcastSourceMetadata.objects.get().simplecast_podcast_id == SIMPLECAST_PODCAST_ID
    assert EpisodeSourceMetadata.objects.count() == 8
    assert Audio.objects.count() == 0
    assert _transcript_count() == 0


def _transcript_count() -> int:
    transcript = cast(Any, apps.get_model("cast", "Transcript"))
    return transcript.objects.count()
