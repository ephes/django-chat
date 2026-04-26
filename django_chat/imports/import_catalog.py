from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.db import transaction

from django_chat.imports.import_sample import (
    AudioCopyResult,
    ImageDownloader,
    ImportPlan,
    ImportSourceData,
    SampleImportResult,
    StreamingAudioDownloader,
    copy_django_chat_catalog_audio,
    default_stream_download_audio,
    import_django_chat_source_data,
)
from django_chat.imports.models import EpisodeSourceMetadata
from django_chat.imports.source_data import (
    RSS_FEED_URL,
    SIMPLECAST_EPISODES_URL,
    SIMPLECAST_PODCAST_ID,
    SIMPLECAST_PODCAST_URL,
    EpisodeSourceData,
    JsonObject,
    RssEpisode,
    RssPodcast,
    SimplecastEpisode,
    SimplecastEpisodePage,
    SimplecastPodcast,
    SimplecastSite,
    SourceLink,
    merge_episode_sources,
    parse_rss_feed,
    parse_simplecast_distribution_links,
    parse_simplecast_episode_detail,
    parse_simplecast_episode_page,
    parse_simplecast_podcast,
    parse_simplecast_site,
)

USER_AGENT = "django-chat-catalog-import/1.0"

JsonFetcher = Callable[[str, float], JsonObject]
TextFetcher = Callable[[str, float], str]


@dataclass(frozen=True)
class CatalogSourceFetchSummary:
    rss_episode_count: int
    simplecast_list_episode_count: int
    simplecast_detail_episode_count: int
    simplecast_page_count: int
    source_link_count: int


@dataclass(frozen=True)
class CatalogSourceData:
    source_data: ImportSourceData
    fetch_summary: CatalogSourceFetchSummary


@dataclass(frozen=True)
class CatalogImportResult:
    import_result: SampleImportResult
    audio_metadata: tuple[AudioCopyResult, ...]
    fetch_summary: CatalogSourceFetchSummary


def load_live_catalog_source_data(
    *,
    timeout: float = 30.0,
    max_episodes: int | None = None,
    simplecast_page_size: int = 100,
    simplecast_max_pages: int | None = None,
    text_fetcher: TextFetcher | None = None,
    json_fetcher: JsonFetcher | None = None,
) -> CatalogSourceData:
    """Fetch live Django Chat RSS and Simplecast source data for catalog import."""

    if max_episodes is not None and max_episodes < 1:
        msg = "--max-episodes must be a positive integer when provided."
        raise ValueError(msg)
    if simplecast_page_size < 1:
        msg = "--simplecast-page-size must be a positive integer."
        raise ValueError(msg)
    if simplecast_max_pages is not None and simplecast_max_pages < 1:
        msg = "--simplecast-max-pages must be a positive integer when provided."
        raise ValueError(msg)

    fetch_text = text_fetcher or default_fetch_text
    fetch_json = json_fetcher or default_fetch_json

    rss_podcast = parse_rss_feed(fetch_text(RSS_FEED_URL, timeout), source_url=RSS_FEED_URL)
    rss_episodes = rss_podcast.episodes[:max_episodes] if max_episodes else rss_podcast.episodes
    if max_episodes:
        rss_podcast = _replace_rss_episodes(rss_podcast, rss_episodes)

    try:
        simplecast_podcast = parse_simplecast_podcast(
            fetch_json(SIMPLECAST_PODCAST_URL, timeout),
            source_url=SIMPLECAST_PODCAST_URL,
        )
    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        json.JSONDecodeError,
    ):
        simplecast_podcast = _fallback_simplecast_podcast(rss_podcast)

    simplecast_site = _load_simplecast_site(simplecast_podcast, fetch_json, timeout=timeout)
    distribution_links = _load_distribution_links(
        simplecast_podcast,
        fetch_json,
        timeout=timeout,
    )
    pages = _load_simplecast_episode_pages(
        fetch_json,
        timeout=timeout,
        max_episodes=max_episodes,
        page_size=simplecast_page_size,
        max_pages=simplecast_max_pages,
    )
    list_episodes = _truncate(
        tuple(episode for page in pages for episode in page.episodes),
        max_episodes,
    )
    detail_episodes = _load_simplecast_episode_details(
        list_episodes,
        fetch_json,
        timeout=timeout,
    )
    simplecast_episodes = (*detail_episodes, *list_episodes)
    source_links = (
        *simplecast_site.menu_links,
        *simplecast_site.social_links,
        *distribution_links,
    )

    source_data = ImportSourceData(
        rss_podcast=rss_podcast,
        simplecast_podcast=simplecast_podcast,
        simplecast_site=simplecast_site,
        source_links=source_links,
        episodes=merge_episode_sources(rss_podcast.episodes, simplecast_episodes),
    )
    return CatalogSourceData(
        source_data=source_data,
        fetch_summary=CatalogSourceFetchSummary(
            rss_episode_count=len(rss_podcast.episodes),
            simplecast_list_episode_count=len(list_episodes),
            simplecast_detail_episode_count=len(detail_episodes),
            simplecast_page_count=len(pages),
            source_link_count=len(source_links),
        ),
    )


def import_django_chat_catalog(
    catalog_source: CatalogSourceData,
    *,
    copy_audio: bool = False,
    audio_downloader: StreamingAudioDownloader | None = None,
    cover_image_downloader: ImageDownloader | None = None,
) -> CatalogImportResult:
    """Import live catalog source data and optionally stream-copy catalog audio."""

    result = import_django_chat_source_data(
        catalog_source.source_data,
        copy_audio=False,
        cover_image_downloader=cover_image_downloader,
    )
    audio_results: tuple[AudioCopyResult, ...] = ()
    if copy_audio:
        metadata = tuple(
            EpisodeSourceMetadata.objects.select_related("episode")
            .filter(pk__in=[item.pk for item in result.episode_metadata])
            .order_by("-source_published_at", "-episode_number", "source_title")
        )
        audio_results = copy_django_chat_catalog_audio(
            metadata,
            audio_downloader=audio_downloader,
        )
        result = SampleImportResult(
            podcast=result.podcast,
            podcast_metadata=result.podcast_metadata,
            source_links=result.source_links,
            episodes=result.episodes,
            episode_metadata=result.episode_metadata,
            audio_metadata=tuple(item.audio_metadata for item in audio_results),
            podcast_created=result.podcast_created,
            episodes_created=result.episodes_created,
            audio_created=sum(1 for item in audio_results if item.audio_created),
            audio_copied=sum(1 for item in audio_results if item.file_copied),
            audio_skipped=sum(1 for item in audio_results if not item.file_copied),
        )

    return CatalogImportResult(
        import_result=result,
        audio_metadata=audio_results,
        fetch_summary=catalog_source.fetch_summary,
    )


def dry_run_catalog_import(catalog_source: CatalogSourceData) -> ImportPlan:
    """Build a catalog plan inside a rollback-only transaction."""

    with transaction.atomic():
        result = import_django_chat_source_data(catalog_source.source_data)
        transaction.set_rollback(True)
    source_plan = build_import_plan(catalog_source.source_data)
    return ImportPlan(
        rss_episode_count=source_plan.rss_episode_count,
        simplecast_episode_count=source_plan.simplecast_episode_count,
        merged_episode_count=len(result.episodes),
        source_link_count=source_plan.source_link_count,
        source_audio_byte_size=source_plan.source_audio_byte_size,
    )


def build_import_plan(source_data: ImportSourceData) -> ImportPlan:
    byte_sizes = [
        byte_size
        for episode in source_data.episodes
        if (byte_size := _episode_audio_byte_size(episode)) is not None
    ]
    source_audio_byte_size = sum(byte_sizes) if byte_sizes else None
    return ImportPlan(
        rss_episode_count=len(source_data.rss_podcast.episodes),
        simplecast_episode_count=len(
            {
                episode.simplecast.id
                for episode in source_data.episodes
                if episode.simplecast is not None
            }
        ),
        merged_episode_count=len(source_data.episodes),
        source_link_count=len(source_data.source_links),
        source_audio_byte_size=source_audio_byte_size,
    )


def default_fetch_text(source_url: str, timeout: float) -> str:
    request = Request(source_url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8")


def _episode_audio_byte_size(episode: EpisodeSourceData) -> int | None:
    if episode.simplecast is not None and episode.simplecast.audio_file_size is not None:
        return episode.simplecast.audio_file_size
    if (
        episode.rss is not None
        and episode.rss.enclosure is not None
        and episode.rss.enclosure.length is not None
    ):
        return episode.rss.enclosure.length
    return None


def default_fetch_json(source_url: str, timeout: float) -> JsonObject:
    payload = json.loads(default_fetch_text(source_url, timeout))
    if not isinstance(payload, dict):
        msg = f"Expected JSON object from {source_url}"
        raise ValueError(msg)
    return payload


def timed_stream_audio_downloader(timeout: float) -> StreamingAudioDownloader:
    def download(source_url: str, destination: Path):
        return default_stream_download_audio(source_url, destination, timeout=timeout)

    return download


def live_cover_image_downloader(timeout: float) -> ImageDownloader:
    def download(source_url: str) -> bytes:
        request = Request(source_url, headers={"User-Agent": USER_AGENT})
        with urlopen(request, timeout=timeout) as response:
            return response.read()

    return download


def _load_simplecast_site(
    podcast: SimplecastPodcast,
    json_fetcher: JsonFetcher,
    *,
    timeout: float,
) -> SimplecastSite:
    if not podcast.site_api_url:
        return _empty_simplecast_site(podcast)
    try:
        return parse_simplecast_site(
            json_fetcher(podcast.site_api_url, timeout),
            source_url=podcast.site_api_url,
        )
    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        json.JSONDecodeError,
    ):
        return _empty_simplecast_site(podcast)


def _load_distribution_links(
    podcast: SimplecastPodcast,
    json_fetcher: JsonFetcher,
    *,
    timeout: float,
) -> tuple[SourceLink, ...]:
    if not podcast.distribution_channels_url:
        return ()
    try:
        return parse_simplecast_distribution_links(
            json_fetcher(podcast.distribution_channels_url, timeout)
        )
    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        json.JSONDecodeError,
    ):
        return ()


def _load_simplecast_episode_pages(
    json_fetcher: JsonFetcher,
    *,
    timeout: float,
    max_episodes: int | None,
    page_size: int,
    max_pages: int | None,
) -> tuple[SimplecastEpisodePage, ...]:
    query = {
        "limit": min(page_size, max_episodes) if max_episodes else page_size,
        "private": "false",
        "sort": "latest",
        "status": "published",
    }
    next_url: str | None = f"{SIMPLECAST_EPISODES_URL}?{urlencode(query)}"
    pages: list[SimplecastEpisodePage] = []
    episode_count = 0
    while next_url:
        if max_pages is not None and len(pages) >= max_pages:
            break
        try:
            page = parse_simplecast_episode_page(
                json_fetcher(next_url, timeout),
                source_url=next_url,
            )
        except (
            OSError,
            ValueError,
            KeyError,
            TypeError,
            json.JSONDecodeError,
        ):
            break
        pages.append(page)
        episode_count += len(page.episodes)
        if max_episodes is not None and episode_count >= max_episodes:
            break
        next_url = page.next_url
    return tuple(pages)


def _load_simplecast_episode_details(
    episodes: tuple[SimplecastEpisode, ...],
    json_fetcher: JsonFetcher,
    *,
    timeout: float,
) -> tuple[SimplecastEpisode, ...]:
    details: list[SimplecastEpisode] = []
    seen_urls: set[str] = set()
    for episode in episodes:
        if not episode.api_url or episode.api_url in seen_urls:
            continue
        seen_urls.add(episode.api_url)
        try:
            details.append(
                parse_simplecast_episode_detail(
                    json_fetcher(episode.api_url, timeout),
                    source_url=episode.api_url,
                )
            )
        except (
            OSError,
            ValueError,
            KeyError,
            TypeError,
            json.JSONDecodeError,
        ):
            continue
    return tuple(details)


def _empty_simplecast_site(podcast: SimplecastPodcast) -> SimplecastSite:
    return SimplecastSite(
        source_url="",
        id=f"{SIMPLECAST_PODCAST_ID}:site-unavailable",
        podcast_id=podcast.id,
        url=None,
        external_website=podcast.website_url,
        cname_url=None,
        theme=None,
        color=None,
        privacy_policy_link=None,
        privacy_policy_text=None,
        legacy_hosts=None,
        menu_links=(),
        social_links=(),
    )


def _fallback_simplecast_podcast(rss_podcast: RssPodcast) -> SimplecastPodcast:
    return SimplecastPodcast(
        source_url=SIMPLECAST_PODCAST_URL,
        id=SIMPLECAST_PODCAST_ID,
        title=rss_podcast.title,
        description=rss_podcast.description,
        language=rss_podcast.language,
        feed_url=rss_podcast.feed_url or rss_podcast.source_url,
        website_url=rss_podcast.website_url,
        image_url=rss_podcast.image_url,
        status=None,
        is_explicit=rss_podcast.explicit,
        episode_count=len(rss_podcast.episodes),
        author_names=(rss_podcast.author,) if rss_podcast.author else (),
        site_id=None,
        site_api_url=None,
        distribution_channels_url=None,
        published_at=rss_podcast.published_at,
        updated_at=rss_podcast.last_build_at,
    )


def _replace_rss_episodes(
    podcast: RssPodcast,
    episodes: tuple[RssEpisode, ...],
) -> RssPodcast:
    return replace(podcast, episodes=episodes)


def _truncate(
    episodes: tuple[SimplecastEpisode, ...],
    max_episodes: int | None,
) -> tuple[SimplecastEpisode, ...]:
    return episodes[:max_episodes] if max_episodes else episodes
