from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from xml.etree import ElementTree

from cast.models import Episode, Podcast
from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.urls import reverse


@dataclass(frozen=True)
class ResponseMeasurement:
    path: str
    status_code: int
    elapsed_ms: float
    query_count: int


@dataclass(frozen=True)
class AudioCompleteness:
    podcast_slug: str
    live_episode_count: int
    with_audio_count: int
    missing_audio_count: int


@dataclass(frozen=True)
class CatalogPerformanceResult:
    feed: ResponseMeasurement
    feed_item_count: int
    latest_entries_feed: ResponseMeasurement
    latest_entries_item_count: int
    episode_list: ResponseMeasurement
    audio_completeness: AudioCompleteness


def measure_catalog_performance(
    *,
    podcast_slug: str | None = None,
    audio_format: str = "mp3",
    host: str = "localhost",
) -> CatalogPerformanceResult:
    """Measure generated feed and episode-index response behavior locally."""

    podcast_slug = podcast_slug or settings.DJANGO_CHAT_PODCAST_SLUG
    client = Client(HTTP_HOST=host)
    feed_path = reverse("cast:podcast_feed_rss", args=[podcast_slug, audio_format])
    cache.clear()
    feed_measurement, feed_content = _measure_response(client, feed_path)
    feed_item_count = _feed_item_count(feed_content) if feed_measurement.status_code == 200 else 0

    latest_entries_feed_path = reverse("cast:latest_entries_feed", args=[podcast_slug])
    cache.clear()
    # Report latest-entries failures as status=500 so incomplete audio state is visible.
    latest_entries_client = Client(HTTP_HOST=host, raise_request_exception=False)
    latest_entries_measurement, latest_entries_content = _measure_response(
        latest_entries_client,
        latest_entries_feed_path,
    )
    latest_entries_item_count = (
        _feed_item_count(latest_entries_content)
        if latest_entries_measurement.status_code == 200
        else 0
    )

    cache.clear()
    list_measurement, _ = _measure_response(client, f"/{podcast_slug}/")
    return CatalogPerformanceResult(
        feed=feed_measurement,
        feed_item_count=feed_item_count,
        latest_entries_feed=latest_entries_measurement,
        latest_entries_item_count=latest_entries_item_count,
        episode_list=list_measurement,
        audio_completeness=measure_audio_completeness(podcast_slug=podcast_slug),
    )


def measure_audio_completeness(*, podcast_slug: str | None = None) -> AudioCompleteness:
    """Count live imported podcast episodes that still lack copied audio."""

    podcast_slug = podcast_slug or settings.DJANGO_CHAT_PODCAST_SLUG
    podcast = Podcast.objects.get(slug=podcast_slug)
    live_episodes = Episode.objects.live().descendant_of(podcast)
    live_episode_count = live_episodes.count()
    with_audio_count = live_episodes.filter(podcast_audio__isnull=False).count()
    return AudioCompleteness(
        podcast_slug=podcast_slug,
        live_episode_count=live_episode_count,
        with_audio_count=with_audio_count,
        missing_audio_count=live_episode_count - with_audio_count,
    )


def format_catalog_performance_result(result: CatalogPerformanceResult) -> str:
    return "\n".join(
        [
            "Django Chat catalog performance measurement",
            (
                "Podcast feed: "
                f"path={result.feed.path}, "
                f"status={result.feed.status_code}, "
                f"elapsed_ms={result.feed.elapsed_ms:.1f}, "
                f"items={result.feed_item_count}, "
                f"queries={result.feed.query_count}"
            ),
            (
                "Latest entries feed: "
                f"path={result.latest_entries_feed.path}, "
                f"status={result.latest_entries_feed.status_code}, "
                f"elapsed_ms={result.latest_entries_feed.elapsed_ms:.1f}, "
                f"items={result.latest_entries_item_count}, "
                f"queries={result.latest_entries_feed.query_count}"
            ),
            (
                "Episode list: "
                f"path={result.episode_list.path}, "
                f"status={result.episode_list.status_code}, "
                f"elapsed_ms={result.episode_list.elapsed_ms:.1f}, "
                f"queries={result.episode_list.query_count}"
            ),
            (
                "Audio completeness: "
                f"podcast_slug={result.audio_completeness.podcast_slug}, "
                f"live_episodes={result.audio_completeness.live_episode_count}, "
                f"with_audio={result.audio_completeness.with_audio_count}, "
                f"missing_audio={result.audio_completeness.missing_audio_count}"
            ),
        ]
    )


def _measure_response(client: Client, path: str) -> tuple[ResponseMeasurement, bytes]:
    with CaptureQueriesContext(connection) as queries:
        started = perf_counter()
        response = client.get(path, secure=True)
        elapsed_ms = (perf_counter() - started) * 1000
    return (
        ResponseMeasurement(
            path=path,
            status_code=response.status_code,
            elapsed_ms=elapsed_ms,
            query_count=len(queries),
        ),
        response.content,
    )


def _feed_item_count(content: bytes) -> int:
    try:
        root = ElementTree.fromstring(content)
    except ElementTree.ParseError:
        return 0
    channel = root.find("channel")
    if channel is None:
        return 0
    return len(channel.findall("item"))
