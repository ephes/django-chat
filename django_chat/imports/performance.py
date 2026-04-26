from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from xml.etree import ElementTree

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
class CatalogPerformanceResult:
    feed: ResponseMeasurement
    feed_item_count: int
    episode_list: ResponseMeasurement


def measure_catalog_performance(
    *,
    podcast_slug: str = "episodes",
    audio_format: str = "mp3",
    host: str = "localhost",
) -> CatalogPerformanceResult:
    """Measure generated feed and episode-index response behavior locally."""

    client = Client(HTTP_HOST=host)
    feed_path = reverse("cast:podcast_feed_rss", args=[podcast_slug, audio_format])
    cache.clear()
    feed_measurement, feed_content = _measure_response(client, feed_path)
    feed_item_count = _feed_item_count(feed_content) if feed_measurement.status_code == 200 else 0

    cache.clear()
    list_measurement, _ = _measure_response(client, f"/{podcast_slug}/")
    return CatalogPerformanceResult(
        feed=feed_measurement,
        feed_item_count=feed_item_count,
        episode_list=list_measurement,
    )


def format_catalog_performance_result(result: CatalogPerformanceResult) -> str:
    return "\n".join(
        [
            "Django Chat catalog performance measurement",
            (
                "Feed: "
                f"path={result.feed.path}, "
                f"status={result.feed.status_code}, "
                f"elapsed_ms={result.feed.elapsed_ms:.1f}, "
                f"items={result.feed_item_count}, "
                f"queries={result.feed.query_count}"
            ),
            (
                "Episode list: "
                f"path={result.episode_list.path}, "
                f"status={result.episode_list.status_code}, "
                f"elapsed_ms={result.episode_list.elapsed_ms:.1f}, "
                f"queries={result.episode_list.query_count}"
            ),
        ]
    )


def _measure_response(client: Client, path: str) -> tuple[ResponseMeasurement, bytes]:
    with CaptureQueriesContext(connection) as queries:
        started = perf_counter()
        response = client.get(path)
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
