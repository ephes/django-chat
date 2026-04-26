from __future__ import annotations

from typing import Any

import pytest
from cast.models import Audio, Episode
from django.apps import apps
from django.test import Client, override_settings
from django.urls import resolve, reverse

from django_chat.imports.import_sample import DownloadedAudio, import_django_chat_sample
from django_chat.imports.models import PodcastSourceLink


@pytest.mark.django_db
def test_root_redirects_to_episode_index(client: Client) -> None:
    response = client.get("/")

    assert response.status_code == 302
    assert response["Location"] == "/episodes/"


@pytest.mark.django_db
def test_imported_sample_index_renders_django_chat_theme_and_source_links(
    client: Client,
) -> None:
    import_django_chat_sample()

    response = client.get("/episodes/")

    assert response.status_code == 200
    assert "cast/django_chat/blog_list_of_posts.html" in [
        template.name for template in response.templates if template.name
    ]
    content = response.content.decode()
    assert "Django Chat" in content
    assert "A biweekly podcast on the Django Web Framework" in content
    assert "Django Tasks - Jake Howard" in content
    assert "/episodes/django-tasks-jake-howard/" in content
    assert "Listen &amp; Subscribe" in content
    assert "https://djangochat.com" in content
    assert "Sponsor Us" in content
    assert "https://docs.google.com/document/" in content
    assert "Fosstodon" in content
    assert "Apple Podcasts" in content
    assert "https://itunes.apple.com/us/podcast/django-chat/id1451536459" in content


@pytest.mark.django_db
def test_imported_sample_episode_detail_renders_without_copied_audio(
    client: Client,
) -> None:
    import_django_chat_sample()

    response = client.get("/episodes/django-tasks-jake-howard/")

    assert response.status_code == 200
    assert "cast/django_chat/episode.html" in [
        template.name for template in response.templates if template.name
    ]
    content = response.content.decode()
    assert "Django Tasks - Jake Howard" in content
    assert "Django-Mantle" in content
    assert "Audio copy pending." in content
    assert "<audio" not in content
    assert _transcript_count() == 0


@pytest.mark.django_db
def test_imported_sample_episode_detail_renders_copied_audio(
    client: Client,
    tmp_path: Any,
) -> None:
    with override_settings(MEDIA_ROOT=tmp_path):
        import_django_chat_sample(copy_audio=True, audio_downloader=FakeAudioDownloader())

    response = client.get("/episodes/django-tasks-jake-howard/")

    assert response.status_code == 200
    content = response.content.decode()
    assert "<podlove-player" in content
    # data-load-mode is intentionally NOT set: django-cast does not ship
    # facade CSS, so the unstyled facade markup conflicts with the loaded
    # player on the rendered page. We let the Vite-loaded init module
    # render the player directly.
    assert "data-load-mode" not in content
    assert "/media/cast_audio/django-chat-sample/django-tasks-jake-howard-" in content
    # The django-vite asset tag must emit the prebuilt Podlove init module on
    # episode pages with copied audio.
    assert "/static/cast/vite/podlovePlayer-" in content
    assert 'type="module"' in content
    assert "Audio copy pending." not in content
    assert Audio.objects.count() == 8
    assert Episode.objects.filter(podcast_audio__isnull=False).count() == 8
    assert _transcript_count() == 0


@pytest.mark.django_db
def test_source_links_are_persisted_for_template_rendering() -> None:
    first_result = import_django_chat_sample()
    source_link_ids = set(PodcastSourceLink.objects.values_list("id", flat=True))

    second_result = import_django_chat_sample()

    assert len(first_result.source_links) == 11
    assert len(second_result.source_links) == 11
    assert set(PodcastSourceLink.objects.values_list("id", flat=True)) == source_link_ids
    assert [link.name for link in first_result.podcast_metadata.visible_menu_links] == [
        "YouTube",
        "Sponsor Us",
        "Fosstodon",
    ]
    assert [link.name for link in first_result.podcast_metadata.visible_social_links] == [
        "Fosstodon"
    ]
    assert {link.name for link in first_result.podcast_metadata.visible_distribution_links} >= {
        "Apple Podcasts",
        "Overcast",
        "Spotify",
        "YouTube",
    }


def test_public_url_reversals_still_match_current_shapes() -> None:
    assert reverse("home") == "/"
    assert reverse("cast:podcast_feed_rss", args=["episodes", "mp3"]) == (
        "/episodes/feed/podcast/mp3/rss.xml"
    )
    assert reverse("cast:latest_entries_feed", args=["episodes"]) == "/episodes/feed/rss.xml"
    assert reverse("cast:feed_detail", args=["episodes"]) == "/episodes/feed/"
    assert reverse("cast:episode-transcript", args=["episodes", "django-tasks-jake-howard"]) == (
        "/episodes/django-tasks-jake-howard/transcript/"
    )
    assert reverse("wagtailadmin_home") == "/cms/"
    assert reverse("cast:styleguide") == "/styleguide/"
    assert resolve("/styleguide/").namespace == "cast"


class FakeAudioDownloader:
    def __call__(self, source_url: str) -> DownloadedAudio:
        return DownloadedAudio(
            content=f"fake audio bytes for {source_url}".encode(),
            content_type="audio/mpeg",
            content_length=123,
            filename="sample.mp3",
        )


def _transcript_count() -> int:
    transcript = apps.get_model("cast", "Transcript")
    return transcript.objects.count()
