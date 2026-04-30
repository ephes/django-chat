from __future__ import annotations

import json
from typing import Any

import pytest
from cast.models import Audio, Episode
from django.apps import apps
from django.conf import settings
from django.core.files.base import ContentFile
from django.test import Client, override_settings
from django.urls import resolve, reverse

from django_chat.imports.import_sample import DownloadedAudio, import_django_chat_sample
from django_chat.imports.models import PodcastSourceLink


@pytest.mark.django_db
def test_root_redirects_to_episode_index(client: Client) -> None:
    response = client.get("/")

    assert response.status_code == 302
    assert response["Location"] == episode_index_path()


@pytest.mark.django_db
def test_imported_sample_index_renders_django_chat_theme_and_source_links(
    client: Client,
) -> None:
    import_django_chat_sample()

    response = client.get(episode_index_path())

    assert response.status_code == 200
    assert "cast/django_chat/blog_list_of_posts.html" in [
        template.name for template in response.templates if template.name
    ]
    content = response.content.decode()
    assert "Django Chat" in content
    assert "A biweekly podcast on the Django Web Framework" in content
    assert "Django Tasks - Jake Howard" in content
    assert episode_detail_path("django-tasks-jake-howard") in content
    assert 'rel="alternate" type="application/rss+xml"' in content
    assert absolute_url(podcast_feed_path()) in content
    assert "Listen &amp; Subscribe" in content
    assert f'href="{feed_detail_path()}"' in content
    assert 'href="https://djangochat.com"' not in content
    assert "Sponsor Us" in content
    assert "https://docs.google.com/document/" in content
    assert "Fosstodon" in content
    assert "Apple Podcasts" in content
    assert "https://itunes.apple.com/us/podcast/django-chat/id1451536459" in content
    assert "Overcast" in content
    assert "https://overcast.fm/itunes1451536459/django-chat" in content

    show_actions = _html_between(content, '<div class="show-actions"', "</div>")
    assert "Listen &amp; Subscribe" in show_actions
    assert f'href="{feed_detail_path()}"' in show_actions
    assert "Apple Podcasts" not in show_actions
    assert "button-secondary" not in show_actions

    link_band = _html_between(content, '<section class="link-band"', "</section>")
    assert "Apple Podcasts" in link_band
    assert "https://itunes.apple.com/us/podcast/django-chat/id1451536459" in link_band


@pytest.mark.django_db
def test_imported_sample_feed_detail_renders_rss_and_distribution_links(
    client: Client,
) -> None:
    import_django_chat_sample()

    response = client.get(feed_detail_path())

    assert response.status_code == 200
    assert "cast/django_chat/feed_detail.html" in [
        template.name for template in response.templates if template.name
    ]
    content = response.content.decode()
    assert "Listen &amp; Subscribe" in content
    assert 'rel="alternate" type="application/rss+xml"' in content
    assert absolute_url(podcast_feed_path()) in content
    assert "MP3 podcast RSS" in content
    assert podcast_feed_path() in content
    assert "/episodes/feed/podcast/m4a/rss.xml" not in content
    assert "/episodes/feed/podcast/oga/rss.xml" not in content
    assert "/episodes/feed/podcast/opus/rss.xml" not in content
    assert "Latest entries RSS for site updates" in content
    assert "<strong>Latest entries RSS</strong>" not in content
    assert "Apple Podcasts" in content
    assert (
        '<a href="https://itunes.apple.com/us/podcast/django-chat/id1451536459"'
        ' target="_blank" rel="noopener noreferrer">Apple Podcasts</a>'
    ) in content
    assert "Overcast" in content
    assert (
        '<a href="https://overcast.fm/itunes1451536459/django-chat"'
        ' target="_blank" rel="noopener noreferrer">Overcast</a>'
    ) in content
    assert "Spotify" in content
    assert "https://open.spotify.com/show/" in content
    assert "podlove-subscribe-button" not in content
    assert "subscribe_button/javascripts/app.js" not in content
    assert "window.podcastData" not in content


@pytest.mark.django_db
def test_feed_detail_canonical_drops_query_strings(client: Client) -> None:
    import_django_chat_sample()

    response = client.get(f"{feed_detail_path()}?utm_source=review")

    assert response.status_code == 200
    content = response.content.decode()
    assert f'<link rel="canonical" href="{absolute_url(feed_detail_path())}">' in content
    assert f'<meta property="og:url" content="{absolute_url(feed_detail_path())}">' in content
    assert "utm_source=review" not in content


@pytest.mark.django_db
def test_imported_sample_episode_detail_renders_without_copied_audio(
    client: Client,
) -> None:
    import_django_chat_sample()

    response = client.get(episode_detail_path("django-tasks-jake-howard"))

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

    response = client.get(episode_detail_path("django-tasks-jake-howard"))

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
def test_imported_sample_episode_surfaces_attached_generated_transcript(
    client: Client,
    tmp_path: Any,
) -> None:
    with override_settings(MEDIA_ROOT=tmp_path):
        import_django_chat_sample(copy_audio=True, audio_downloader=FakeAudioDownloader())
        episode = Episode.objects.get(slug="django-tasks-jake-howard")
        assert episode.podcast_audio is not None
        transcript = _create_generated_transcript(episode.podcast_audio)

        detail_response = client.get(episode_detail_path("django-tasks-jake-howard"))
        transcript_response = client.get(transcript_path("django-tasks-jake-howard"))
        podlove_response = client.get(
            reverse(
                "cast:api:audio_podlove_detail",
                kwargs={"pk": episode.podcast_audio.pk, "post_id": episode.pk},
            )
        )

    assert detail_response.status_code == 200
    detail_content = detail_response.content.decode()
    assert f'href="{absolute_url(transcript_path("django-tasks-jake-howard"))}"' in detail_content
    assert "<podlove-player" in detail_content

    assert transcript_response.status_code == 200
    assert "cast/django_chat/transcript.html" in [
        template.name for template in transcript_response.templates if template.name
    ]
    transcript_content = transcript_response.content.decode()
    assert "Transcript: Django Tasks - Jake Howard" in transcript_content
    assert "Generated transcript segment for an imported episode." in transcript_content

    assert podlove_response.status_code == 200
    podlove_data = podlove_response.json()
    assert len(podlove_data["transcripts"]) == 1
    podlove_transcript = podlove_data["transcripts"][0]
    assert podlove_transcript["start"] == "00:00:00.000"
    assert podlove_transcript["end"] == "00:00:02.000"
    assert podlove_transcript["speaker"] == "Host"
    assert podlove_transcript["text"] == "Generated transcript segment for an imported episode."
    transcript_model = apps.get_model("cast", "Transcript")
    assert transcript_model.objects.get(pk=transcript.pk).audio == episode.podcast_audio


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
    slug = podcast_slug()

    assert reverse("home") == "/"
    assert (
        reverse("cast:podcast_feed_rss", args=[slug, "mp3"]) == f"/{slug}/feed/podcast/mp3/rss.xml"
    )
    assert reverse("cast:latest_entries_feed", args=[slug]) == f"/{slug}/feed/rss.xml"
    assert reverse("cast:feed_detail", args=[slug]) == f"/{slug}/feed/"
    assert (
        reverse("cast:episode-transcript", args=[slug, "django-tasks-jake-howard"])
        == f"/{slug}/django-tasks-jake-howard/transcript/"
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


def _create_generated_transcript(audio: Audio) -> Any:
    transcript_model = apps.get_model("cast", "Transcript")
    transcript = transcript_model.objects.create(audio=audio)
    podlove = {
        "transcripts": [
            {
                "start": "00:00:00.000",
                "start_ms": 0,
                "end": "00:00:02.000",
                "end_ms": 2000,
                "speaker": "Host",
                "voice": "",
                "text": "Generated transcript segment for an imported episode.",
            }
        ]
    }
    dote = {
        "lines": [
            {
                "startTime": "00:00:00,000",
                "endTime": "00:00:02,000",
                "speakerDesignation": "Host",
                "text": "Generated transcript segment for an imported episode.",
            }
        ]
    }
    transcript.podlove.save("podlove.json", ContentFile(json.dumps(podlove)))
    transcript.vtt.save(
        "transcript.vtt",
        ContentFile(
            "WEBVTT\n\n"
            "00:00:00.000 --> 00:00:02.000\n"
            "Generated transcript segment for an imported episode.\n"
        ),
    )
    transcript.dote.save("dote.json", ContentFile(json.dumps(dote)))
    return transcript


def _html_between(content: str, start: str, end: str) -> str:
    assert start in content
    fragment = content.split(start, maxsplit=1)[1]
    assert end in fragment
    return fragment.split(end, maxsplit=1)[0]


def podcast_slug() -> str:
    return settings.DJANGO_CHAT_PODCAST_SLUG


def episode_index_path() -> str:
    return reverse("django_chat_episode_index")


def feed_detail_path() -> str:
    return reverse("cast:feed_detail", args=[podcast_slug()])


def podcast_feed_path() -> str:
    return reverse("cast:podcast_feed_rss", args=[podcast_slug(), "mp3"])


def latest_entries_feed_path() -> str:
    return reverse("cast:latest_entries_feed", args=[podcast_slug()])


def episode_detail_path(slug: str) -> str:
    return f"/{podcast_slug()}/{slug}/"


def transcript_path(slug: str) -> str:
    return reverse("cast:episode-transcript", args=[podcast_slug(), slug])


def absolute_url(path: str) -> str:
    return f"http://testserver{path}"
