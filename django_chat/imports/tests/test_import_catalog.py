from __future__ import annotations

from dataclasses import replace
from io import StringIO
from pathlib import Path
from typing import Any

import pytest
from cast.models import Audio, Episode
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings

from django_chat.imports.import_catalog import (
    CatalogSourceData,
    CatalogSourceFetchSummary,
    build_import_plan,
    import_django_chat_catalog,
    load_live_catalog_source_data,
)
from django_chat.imports.import_sample import (
    DownloadedAudioFile,
    ImportSourceData,
    load_sample_source_data,
)
from django_chat.imports.models import EpisodeAudioImportMetadata, EpisodeSourceMetadata
from django_chat.imports.source_data import (
    RSS_FEED_URL,
    SIMPLECAST_DISTRIBUTION_CHANNELS_URL,
    SIMPLECAST_EPISODES_URL,
    SIMPLECAST_PODCAST_URL,
    RssEnclosure,
    RssEpisode,
    merge_episode_sources,
)


def test_live_catalog_loader_follows_simplecast_pagination_and_details() -> None:
    json_fetcher = FakeCatalogJsonFetcher()

    catalog = load_live_catalog_source_data(
        timeout=12.5,
        max_episodes=3,
        simplecast_page_size=2,
        text_fetcher=lambda _url, _timeout: _rss_xml(3),
        json_fetcher=json_fetcher,
    )

    assert catalog.fetch_summary.rss_episode_count == 3
    assert catalog.fetch_summary.simplecast_page_count == 2
    assert catalog.fetch_summary.simplecast_list_episode_count == 3
    assert catalog.fetch_summary.simplecast_detail_episode_count == 3
    assert catalog.fetch_summary.source_link_count == 2
    assert len(catalog.source_data.episodes) == 3
    assert [episode.episode_number for episode in catalog.source_data.episodes] == [3, 2, 1]
    assert all(episode.simplecast is not None for episode in catalog.source_data.episodes)
    assert any(
        url.startswith(SIMPLECAST_EPISODES_URL) and "limit=2" in url for url in json_fetcher.urls
    )
    assert "https://api.simplecast.com/page-2" in json_fetcher.urls


def test_live_catalog_loader_falls_back_to_rss_when_simplecast_is_unavailable() -> None:
    catalog = load_live_catalog_source_data(
        max_episodes=2,
        text_fetcher=lambda _url, _timeout: _rss_xml(2),
        json_fetcher=FailingJsonFetcher(),
    )

    assert catalog.fetch_summary.rss_episode_count == 2
    assert catalog.fetch_summary.simplecast_page_count == 0
    assert catalog.fetch_summary.simplecast_list_episode_count == 0
    assert len(catalog.source_data.episodes) == 2
    assert all(episode.simplecast is None for episode in catalog.source_data.episodes)


@pytest.mark.django_db
def test_catalog_import_can_import_more_than_fixture_sample() -> None:
    catalog = _fake_catalog_source(extra_episode_count=2)

    result = import_django_chat_catalog(catalog)

    assert result.import_result.episodes_created == 10
    assert Episode.objects.count() == 10
    assert EpisodeSourceMetadata.objects.count() == 10
    assert EpisodeAudioImportMetadata.objects.count() == 0


def test_catalog_import_plan_mixes_simplecast_and_rss_audio_sizes() -> None:
    catalog = _fake_catalog_source(extra_episode_count=1)

    plan = build_import_plan(catalog.source_data)

    previous_simplecast_only_size = sum(
        episode.simplecast.audio_file_size or 0
        for episode in catalog.source_data.episodes
        if episode.simplecast is not None
    )
    expected_size = sum(
        (
            episode.simplecast.audio_file_size
            if episode.simplecast is not None and episode.simplecast.audio_file_size is not None
            else episode.rss.enclosure.length
        )
        for episode in catalog.source_data.episodes
        if episode.rss is not None and episode.rss.enclosure is not None
    )
    assert expected_size > previous_simplecast_only_size
    assert plan.source_audio_byte_size == expected_size


@pytest.mark.django_db
def test_import_catalog_management_command_dry_run_rolls_back(
    monkeypatch: Any,
) -> None:
    catalog = _fake_catalog_source(extra_episode_count=1)

    monkeypatch.setattr(
        "django_chat.imports.management.commands.import_django_chat_catalog."
        "load_live_catalog_source_data",
        lambda **_kwargs: catalog,
    )
    stdout = StringIO()

    call_command("import_django_chat_catalog", "--dry-run", "--max-episodes=3", stdout=stdout)

    output = stdout.getvalue()
    assert "Fetched Django Chat catalog source data" in output
    assert "Dry-run catalog import rolled back" in output
    assert Episode.objects.count() == 0
    assert EpisodeSourceMetadata.objects.count() == 0


def test_import_catalog_management_command_rejects_cover_image_dry_run() -> None:
    with pytest.raises(CommandError, match="--copy-cover-image cannot be combined"):
        call_command("import_django_chat_catalog", "--dry-run", "--copy-cover-image")


def test_import_catalog_management_command_rejects_audio_dry_run() -> None:
    with pytest.raises(CommandError, match="--copy-audio cannot be combined"):
        call_command("import_django_chat_catalog", "--dry-run", "--copy-audio")


@pytest.mark.django_db
def test_catalog_streaming_audio_copy_is_idempotent(tmp_path: Path) -> None:
    catalog = _fake_catalog_source(extra_episode_count=1)
    downloader = FakeStreamingAudioDownloader()

    with override_settings(MEDIA_ROOT=tmp_path):
        first = import_django_chat_catalog(
            catalog,
            copy_audio=True,
            audio_downloader=downloader,
        )
        audio_ids = set(Audio.objects.values_list("id", flat=True))
        audio_metadata_ids = set(EpisodeAudioImportMetadata.objects.values_list("id", flat=True))
        episode_ids = set(Episode.objects.values_list("id", flat=True))
        second = import_django_chat_catalog(
            catalog,
            copy_audio=True,
            audio_downloader=FailingStreamingAudioDownloader(),
        )

    assert first.import_result.audio_created == 9
    assert first.import_result.audio_copied == 9
    assert first.import_result.audio_skipped == 0
    assert second.import_result.audio_created == 0
    assert second.import_result.audio_copied == 0
    assert second.import_result.audio_skipped == 9
    assert len(downloader.urls) == 9
    assert set(Audio.objects.values_list("id", flat=True)) == audio_ids
    assert set(EpisodeAudioImportMetadata.objects.values_list("id", flat=True)) == (
        audio_metadata_ids
    )
    assert set(Episode.objects.values_list("id", flat=True)) == episode_ids
    assert Episode.objects.count() == 9
    assert EpisodeAudioImportMetadata.objects.count() == 9
    assert all(
        storage_name.startswith("cast_audio/django-chat-catalog/")
        for storage_name in EpisodeAudioImportMetadata.objects.values_list(
            "storage_name",
            flat=True,
        )
    )


@pytest.mark.django_db
def test_import_catalog_management_command_uses_limiter_option(monkeypatch: Any) -> None:
    seen_options: dict[str, Any] = {}

    def fake_loader(**kwargs: Any) -> CatalogSourceData:
        seen_options.update(kwargs)
        return _fake_catalog_source(extra_episode_count=0)

    monkeypatch.setattr(
        "django_chat.imports.management.commands.import_django_chat_catalog."
        "load_live_catalog_source_data",
        fake_loader,
    )
    stdout = StringIO()

    call_command("import_django_chat_catalog", "--max-episodes=3", stdout=stdout)

    assert seen_options["max_episodes"] == 3
    assert "episodes_total=8" in stdout.getvalue()
    assert Episode.objects.count() == 8


class FakeCatalogJsonFetcher:
    def __init__(self) -> None:
        self.urls: list[str] = []

    def __call__(self, source_url: str, _timeout: float) -> dict[str, Any]:
        self.urls.append(source_url)
        if source_url == SIMPLECAST_PODCAST_URL:
            return {
                "href": SIMPLECAST_PODCAST_URL,
                "id": "19d48b52-7d9d-4294-8dbf-7f2739ba2e91",
                "title": "Django Chat",
                "feed_url": RSS_FEED_URL,
                "site": {"href": "https://api.simplecast.com/sites/site-id", "id": "site-id"},
                "distribution_channels": {"href": SIMPLECAST_DISTRIBUTION_CHANNELS_URL},
                "episodes": {"count": 3},
            }
        if source_url == "https://api.simplecast.com/sites/site-id":
            return {
                "href": source_url,
                "id": "site-id",
                "podcast": {"id": "19d48b52-7d9d-4294-8dbf-7f2739ba2e91"},
                "menu_links": {
                    "collection": [
                        {"id": "youtube", "name": "YouTube", "url": "https://youtube.test"}
                    ]
                },
                "site_links": {"collection": []},
            }
        if source_url == SIMPLECAST_DISTRIBUTION_CHANNELS_URL:
            return {
                "collection": [
                    {
                        "id": "apple",
                        "href": "https://api.simplecast.com/distribution/apple",
                        "url": "https://podcasts.apple.test/django-chat",
                        "distribution_channel": {"id": "apple", "name": "Apple Podcasts"},
                    }
                ]
            }
        if source_url.startswith(SIMPLECAST_EPISODES_URL):
            return _episode_page_payload(
                source_url,
                episodes=[3, 2],
                next_url="https://api.simplecast.com/page-2",
            )
        if source_url == "https://api.simplecast.com/page-2":
            return _episode_page_payload(source_url, episodes=[1], next_url=None)
        if source_url.startswith("https://api.simplecast.com/episodes/"):
            number = int(source_url.rsplit("-", 1)[1])
            return _episode_payload(number, source_kind="detail")
        msg = f"Unexpected URL {source_url}"
        raise AssertionError(msg)


class FailingJsonFetcher:
    def __call__(self, source_url: str, _timeout: float) -> dict[str, Any]:
        raise OSError(source_url)


class FakeStreamingAudioDownloader:
    def __init__(self) -> None:
        self.urls: list[str] = []

    def __call__(self, source_url: str, destination: Path) -> DownloadedAudioFile:
        self.urls.append(source_url)
        content = f"streamed fake audio for {source_url}".encode()
        destination.write_bytes(content)
        return DownloadedAudioFile(
            path=destination,
            byte_size=len(content),
            content_type="audio/mpeg",
            content_length=len(content),
            filename="catalog.mp3",
        )


class FailingStreamingAudioDownloader:
    def __call__(self, source_url: str, destination: Path) -> DownloadedAudioFile:
        msg = f"Unexpected streaming audio download: {source_url}"
        raise AssertionError(msg)


def _fake_catalog_source(*, extra_episode_count: int) -> CatalogSourceData:
    sample = load_sample_source_data()
    extra_rss = tuple(_extra_rss_episode(index) for index in range(extra_episode_count))
    rss_podcast = replace(sample.rss_podcast, episodes=(*sample.rss_podcast.episodes, *extra_rss))
    episodes = merge_episode_sources(rss_podcast.episodes, ())
    # Keep the richer sample Simplecast data for the original fixtures.
    by_key = {episode.matching_key: episode for episode in sample.episodes}
    merged = tuple(by_key.get(episode.matching_key, episode) for episode in episodes)
    source_data = ImportSourceData(
        rss_podcast=rss_podcast,
        simplecast_podcast=sample.simplecast_podcast,
        simplecast_site=sample.simplecast_site,
        source_links=sample.source_links,
        episodes=merged,
    )
    return CatalogSourceData(
        source_data=source_data,
        fetch_summary=CatalogSourceFetchSummary(
            rss_episode_count=len(rss_podcast.episodes),
            simplecast_list_episode_count=len(sample.episodes),
            simplecast_detail_episode_count=4,
            simplecast_page_count=1,
            source_link_count=len(sample.source_links),
        ),
    )


def _extra_rss_episode(index: int) -> RssEpisode:
    number = 10_000 + index
    guid = f"00000000-0000-4000-8000-{number:012d}"
    return RssEpisode(
        source_url=RSS_FEED_URL,
        guid=guid,
        guid_is_permalink=False,
        title=f"Extra Catalog Episode {number}",
        published_at=None,
        description_html=f"<p>Extra episode {number}</p>",
        content_html=f"<p>Extra episode {number} details</p>",
        author="Django Chat",
        link=f"https://djangochat.com/episodes/extra-{number}",
        duration_seconds=60,
        episode_number=number,
        episode_type="full",
        explicit=False,
        enclosure=RssEnclosure(
            url=f"https://media.example.com/extra-{number}.mp3",
            media_type="audio/mpeg",
            length=1234,
        ),
    )


def _rss_xml(count: int) -> str:
    items = "\n".join(_rss_item(number) for number in range(count, 0, -1))
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss xmlns:atom="http://www.w3.org/2005/Atom"
     xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"
     version="2.0">
  <channel>
    <atom:link rel="self" href="{RSS_FEED_URL}" />
    <title>Django Chat</title>
    <description>Django Chat source feed</description>
    <link>https://djangochat.com</link>
    <itunes:author>Django Chat</itunes:author>
    <itunes:explicit>false</itunes:explicit>
    {items}
  </channel>
</rss>"""


def _rss_item(number: int) -> str:
    guid = _guid(number)
    return f"""
    <item>
      <guid isPermaLink="false">{guid}</guid>
      <title>Catalog Episode {number}</title>
      <pubDate>Wed, 15 Apr 2026 08:00:00 +0000</pubDate>
      <description><![CDATA[<p>Episode {number}</p>]]></description>
      <itunes:duration>00:01:00</itunes:duration>
      <itunes:episode>{number}</itunes:episode>
      <itunes:explicit>false</itunes:explicit>
      <enclosure url="https://media.example.com/{number}.mp3" type="audio/mpeg" length="1234" />
    </item>"""


def _episode_page_payload(
    source_url: str,
    *,
    episodes: list[int],
    next_url: str | None,
) -> dict[str, Any]:
    return {
        "href": source_url,
        "count": 3,
        "pages": {
            "current": 1,
            "limit": len(episodes),
            "total": 2,
            "next": {"href": next_url} if next_url else None,
        },
        "collection": [_episode_payload(number, source_kind="list") for number in episodes],
    }


def _episode_payload(number: int, *, source_kind: str) -> dict[str, Any]:
    return {
        "href": f"https://api.simplecast.com/episodes/episode-{number}",
        "id": f"episode-{number}",
        "guid": _guid(number),
        "slug": f"catalog-episode-{number}",
        "title": f"Catalog Episode {number}",
        "number": number,
        "duration": 60,
        "description": f"Episode {number} summary",
        "long_description": f"<p>Episode {number} detail from {source_kind}</p>",
        "audio_file_url": f"https://cdn.simplecast.test/{number}.mp3",
        "audio_file_size": 1234,
        "enclosure_url": f"https://podtrac.test/{number}.mp3",
        "status": "published",
        "is_explicit": False,
    }


def _guid(number: int) -> str:
    return f"00000000-0000-4000-8000-{number:012d}"
