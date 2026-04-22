from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from cast.models import Episode, Podcast
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.html import strip_tags
from django.utils.text import slugify
from wagtail.models import Page, Site

from django_chat.imports.models import EpisodeSourceMetadata, PodcastSourceMetadata
from django_chat.imports.source_data import (
    EpisodeSourceData,
    RssPodcast,
    SimplecastEpisode,
    SimplecastPodcast,
    SimplecastSite,
    merge_episode_sources,
    parse_rss_feed,
    parse_simplecast_episode_detail,
    parse_simplecast_episode_page,
    parse_simplecast_podcast,
    parse_simplecast_site,
)

DEFAULT_SOURCE_FIXTURE_DIR = Path(__file__).parent / "tests" / "fixtures" / "django_chat_source"
PODCAST_PAGE_SLUG = "episodes"

DETAIL_FIXTURE_FILENAMES = (
    "simplecast_episode_detail_0_preview.json",
    "simplecast_episode_detail_1_what-is-django.json",
    "simplecast_episode_detail_2_how-to-learn-django.json",
    "simplecast_episode_detail_200_django-tasks-jake-howard.json",
)


@dataclass(frozen=True)
class SampleSourceData:
    rss_podcast: RssPodcast
    simplecast_podcast: SimplecastPodcast
    simplecast_site: SimplecastSite
    episodes: tuple[EpisodeSourceData, ...]


@dataclass(frozen=True)
class SampleImportResult:
    podcast: Podcast
    podcast_metadata: PodcastSourceMetadata
    episodes: tuple[Episode, ...]
    episode_metadata: tuple[EpisodeSourceMetadata, ...]
    podcast_created: bool
    episodes_created: int


def load_sample_source_data(
    fixture_dir: Path | str = DEFAULT_SOURCE_FIXTURE_DIR,
) -> SampleSourceData:
    fixture_path = Path(fixture_dir)
    rss_podcast = parse_rss_feed(_read_text(fixture_path, "rss_feed.xml"))
    simplecast_podcast = parse_simplecast_podcast(
        _read_json(fixture_path, "simplecast_podcast.json")
    )
    simplecast_site = parse_simplecast_site(_read_json(fixture_path, "simplecast_site.json"))
    simplecast_episodes = (
        *_load_simplecast_detail_episodes(fixture_path),
        *parse_simplecast_episode_page(
            _read_json(fixture_path, "simplecast_episode_list_latest.json")
        ).episodes,
        *parse_simplecast_episode_page(
            _read_json(fixture_path, "simplecast_episode_list_oldest.json")
        ).episodes,
    )

    return SampleSourceData(
        rss_podcast=rss_podcast,
        simplecast_podcast=simplecast_podcast,
        simplecast_site=simplecast_site,
        episodes=merge_episode_sources(rss_podcast.episodes, simplecast_episodes),
    )


@transaction.atomic
def import_django_chat_sample(
    fixture_dir: Path | str = DEFAULT_SOURCE_FIXTURE_DIR,
) -> SampleImportResult:
    source_data = load_sample_source_data(fixture_dir)
    parent_page = _get_podcast_parent_page()
    podcast, podcast_created = _get_or_create_podcast_page(
        parent_page,
        source_data.rss_podcast,
        source_data.simplecast_podcast,
    )
    _update_podcast_page(podcast, source_data.rss_podcast, source_data.simplecast_podcast)
    podcast_metadata = _update_podcast_metadata(
        podcast,
        source_data.rss_podcast,
        source_data.simplecast_podcast,
        source_data.simplecast_site,
    )

    episodes: list[Episode] = []
    episode_metadata: list[EpisodeSourceMetadata] = []
    episodes_created = 0
    for episode_source in source_data.episodes:
        episode, episode_created = _get_or_create_episode_page(podcast, episode_source)
        _update_episode_page(episode, episode_source)
        episodes.append(episode)
        episode_metadata.append(_update_episode_metadata(episode, episode_source))
        if episode_created:
            episodes_created += 1

    return SampleImportResult(
        podcast=podcast,
        podcast_metadata=podcast_metadata,
        episodes=tuple(episodes),
        episode_metadata=tuple(episode_metadata),
        podcast_created=podcast_created,
        episodes_created=episodes_created,
    )


def _load_simplecast_detail_episodes(fixture_path: Path) -> tuple[SimplecastEpisode, ...]:
    return tuple(
        parse_simplecast_episode_detail(_read_json(fixture_path, filename))
        for filename in DETAIL_FIXTURE_FILENAMES
    )


def _get_podcast_parent_page() -> Page:
    default_site = Site.objects.select_related("root_page").filter(is_default_site=True).first()
    if default_site is not None:
        return default_site.root_page.specific

    root_page = Page.get_first_root_node()
    if root_page is None:
        msg = "Wagtail does not have a root page. Run migrations before importing."
        raise RuntimeError(msg)
    return root_page.specific


def _get_or_create_podcast_page(
    parent_page: Page,
    rss_podcast: RssPodcast,
    simplecast_podcast: SimplecastPodcast,
) -> tuple[Podcast, bool]:
    metadata = (
        PodcastSourceMetadata.objects.select_related("podcast")
        .filter(simplecast_podcast_id=simplecast_podcast.id)
        .first()
    )
    if metadata is not None:
        return cast(Podcast, metadata.podcast), False

    existing = Podcast.objects.child_of(parent_page).filter(slug=PODCAST_PAGE_SLUG).first()
    if existing is not None:
        return existing, False

    podcast = Podcast(title=simplecast_podcast.title or rss_podcast.title, slug=PODCAST_PAGE_SLUG)
    _update_podcast_page_fields(podcast, rss_podcast, simplecast_podcast)
    parent_page.add_child(instance=podcast)
    return podcast, True


def _update_podcast_page(
    podcast: Podcast,
    rss_podcast: RssPodcast,
    simplecast_podcast: SimplecastPodcast,
) -> None:
    _update_podcast_page_fields(podcast, rss_podcast, simplecast_podcast)
    podcast.save()


def _update_podcast_page_fields(
    podcast: Podcast,
    rss_podcast: RssPodcast,
    simplecast_podcast: SimplecastPodcast,
) -> None:
    description = simplecast_podcast.description or rss_podcast.description or ""
    title = simplecast_podcast.title or rss_podcast.title
    page = cast(Any, podcast)
    page.title = title
    page.draft_title = title
    page.slug = PODCAST_PAGE_SLUG
    page.author = _join_text(simplecast_podcast.author_names) or rss_podcast.author
    page.email = rss_podcast.owner_email
    page.subtitle = _truncate(strip_tags(description), 255)
    page.description = description
    page.search_description = strip_tags(description)
    page.comments_enabled = False
    page.itunes_categories = json.dumps(
        {category: [] for category in rss_podcast.categories},
        sort_keys=True,
    )
    page.keywords = _truncate(_join_text(rss_podcast.keywords), 255)
    page.explicit = _explicit_choice(
        simplecast_podcast.is_explicit
        if simplecast_podcast.is_explicit is not None
        else rss_podcast.explicit
    )


def _update_podcast_metadata(
    podcast: Podcast,
    rss_podcast: RssPodcast,
    simplecast_podcast: SimplecastPodcast,
    simplecast_site: SimplecastSite,
) -> PodcastSourceMetadata:
    metadata, _ = PodcastSourceMetadata.objects.update_or_create(
        simplecast_podcast_id=simplecast_podcast.id,
        defaults={
            "podcast": podcast,
            "rss_feed_url": rss_podcast.feed_url or rss_podcast.source_url,
            "simplecast_source_url": simplecast_podcast.source_url,
            "site_source_url": simplecast_site.source_url,
            "website_url": simplecast_podcast.website_url or rss_podcast.website_url or "",
            "image_url": simplecast_podcast.image_url or rss_podcast.image_url or "",
            "source_title": simplecast_podcast.title or rss_podcast.title,
            "source_description": simplecast_podcast.description or rss_podcast.description or "",
            "source_is_explicit": simplecast_podcast.is_explicit
            if simplecast_podcast.is_explicit is not None
            else rss_podcast.explicit,
            "source_episode_count": simplecast_podcast.episode_count,
            "source_published_at": simplecast_podcast.published_at or rss_podcast.published_at,
            "source_updated_at": simplecast_podcast.updated_at or rss_podcast.last_build_at,
        },
    )
    return metadata


def _get_or_create_episode_page(
    podcast: Podcast,
    episode_source: EpisodeSourceData,
) -> tuple[Episode, bool]:
    metadata_lookup = Q(matching_key=episode_source.matching_key)
    if episode_source.rss_guid:
        metadata_lookup |= Q(rss_guid=episode_source.rss_guid)
    if episode_source.simplecast_episode_id:
        metadata_lookup |= Q(simplecast_episode_id=episode_source.simplecast_episode_id)
    if episode_source.slug:
        metadata_lookup |= Q(simplecast_slug=episode_source.slug)

    metadata = (
        EpisodeSourceMetadata.objects.select_related("episode").filter(metadata_lookup).first()
    )
    if metadata is not None:
        return cast(Episode, metadata.episode), False

    slug = _episode_slug(episode_source)
    existing = Episode.objects.child_of(podcast).filter(slug=slug).first()
    if existing is not None:
        return existing, False

    episode = Episode(title=episode_source.title, slug=slug)
    _update_episode_page_fields(episode, episode_source)
    podcast.add_child(instance=episode)
    return episode, True


def _update_episode_page(episode: Episode, episode_source: EpisodeSourceData) -> None:
    _update_episode_page_fields(episode, episode_source)
    episode.save()


def _update_episode_page_fields(episode: Episode, episode_source: EpisodeSourceData) -> None:
    description = _episode_description(episode_source)
    page = cast(Any, episode)
    page.title = episode_source.title
    page.draft_title = episode_source.title
    page.slug = _episode_slug(episode_source)
    page.visible_date = episode_source.published_at or timezone.now()
    page.body = _episode_body(episode_source)
    page.search_description = strip_tags(description)
    page.comments_enabled = False
    page.keywords = ""
    page.explicit = _episode_explicit_choice(episode_source)
    page.block = False


def _update_episode_metadata(
    episode: Episode,
    episode_source: EpisodeSourceData,
) -> EpisodeSourceMetadata:
    existing = EpisodeSourceMetadata.objects.filter(
        matching_key=episode_source.matching_key
    ).first()
    if existing is None and episode_source.rss_guid:
        existing = EpisodeSourceMetadata.objects.filter(rss_guid=episode_source.rss_guid).first()
    if existing is None and episode_source.simplecast_episode_id:
        existing = EpisodeSourceMetadata.objects.filter(
            simplecast_episode_id=episode_source.simplecast_episode_id
        ).first()
    if existing is None and episode_source.slug:
        existing = EpisodeSourceMetadata.objects.filter(simplecast_slug=episode_source.slug).first()

    metadata_fields = _episode_metadata_fields(episode, episode_source)
    if existing is None:
        return EpisodeSourceMetadata.objects.create(**metadata_fields)

    for field_name, value in metadata_fields.items():
        setattr(existing, field_name, value)
    existing.save()
    return existing


def _episode_metadata_fields(
    episode: Episode,
    episode_source: EpisodeSourceData,
) -> dict[str, Any]:
    rss = episode_source.rss
    simplecast = episode_source.simplecast

    return {
        "episode": episode,
        "matching_key": episode_source.matching_key,
        "rss_guid": episode_source.rss_guid or "",
        "simplecast_episode_id": episode_source.simplecast_episode_id or "",
        "simplecast_slug": episode_source.slug or "",
        "episode_number": episode_source.episode_number,
        "source_title": episode_source.title,
        "rss_source_url": rss.source_url if rss else "",
        "simplecast_source_url": simplecast.source_url if simplecast else "",
        "simplecast_api_url": simplecast.api_url if simplecast and simplecast.api_url else "",
        "simplecast_episode_url": (
            simplecast.episode_url if simplecast and simplecast.episode_url else ""
        ),
        "original_rss_enclosure_url": episode_source.rss_enclosure_url or "",
        "simplecast_enclosure_url": episode_source.simplecast_enclosure_url or "",
        "simplecast_audio_file_url": simplecast.audio_file_url
        if simplecast and simplecast.audio_file_url
        else "",
        "audio_file_size": simplecast.audio_file_size if simplecast else None,
        "duration_seconds": _duration_seconds(episode_source),
        "rss_description_html": rss.description_html if rss and rss.description_html else "",
        "rss_content_html": rss.content_html if rss and rss.content_html else "",
        "rss_is_explicit": rss.explicit if rss else None,
        "simplecast_description": (
            simplecast.description if simplecast and simplecast.description else ""
        ),
        "simplecast_long_description_html": simplecast.long_description_html
        if simplecast and simplecast.long_description_html
        else "",
        "simplecast_transcript_html": simplecast.transcript_html
        if simplecast and simplecast.transcript_html
        else "",
        "simplecast_is_explicit": simplecast.is_explicit if simplecast else None,
        "source_published_at": episode_source.published_at,
        "source_updated_at": simplecast.updated_at if simplecast else None,
    }


def _episode_body(episode_source: EpisodeSourceData) -> list[tuple[str, list[tuple[str, str]]]]:
    overview = _episode_summary(episode_source)
    detail = _episode_description(episode_source)
    body: list[tuple[str, list[tuple[str, str]]]] = []
    if overview:
        body.append(("overview", [("paragraph", overview)]))
    if detail and detail != overview:
        body.append(("detail", [("paragraph", detail)]))
    if not body and episode_source.title:
        body.append(("overview", [("paragraph", episode_source.title)]))
    return body


def _episode_summary(episode_source: EpisodeSourceData) -> str:
    simplecast = episode_source.simplecast
    rss = episode_source.rss
    if simplecast and simplecast.description:
        return simplecast.description
    if rss and rss.description_html:
        return rss.description_html
    return ""


def _episode_description(episode_source: EpisodeSourceData) -> str:
    simplecast = episode_source.simplecast
    rss = episode_source.rss
    if simplecast and simplecast.long_description_html:
        return simplecast.long_description_html
    if rss and rss.content_html:
        return rss.content_html
    return _episode_summary(episode_source)


def _episode_slug(episode_source: EpisodeSourceData) -> str:
    if episode_source.slug:
        return episode_source.slug
    if episode_source.episode_number is not None:
        return f"episode-{episode_source.episode_number}-{slugify(episode_source.title)}"
    return slugify(episode_source.title) or slugify(episode_source.matching_key)


def _episode_explicit_choice(episode_source: EpisodeSourceData) -> int:
    simplecast = episode_source.simplecast
    rss = episode_source.rss
    explicit = simplecast.is_explicit if simplecast and simplecast.is_explicit is not None else None
    if explicit is None and rss is not None:
        explicit = rss.explicit
    return _explicit_choice(explicit)


def _explicit_choice(is_explicit: bool | None) -> int:
    if is_explicit is True:
        return 1
    if is_explicit is False:
        return 2
    return 3


def _duration_seconds(episode_source: EpisodeSourceData) -> int | None:
    simplecast = episode_source.simplecast
    rss = episode_source.rss
    if simplecast and simplecast.duration_seconds is not None:
        return simplecast.duration_seconds
    if rss and rss.duration_seconds is not None:
        return rss.duration_seconds
    return None


def _join_text(values: tuple[str, ...]) -> str:
    return ", ".join(values)


def _truncate(value: str, max_length: int) -> str:
    if len(value) <= max_length:
        return value
    return value[: max_length - 3].rstrip() + "..."


def _read_text(fixture_path: Path, filename: str) -> str:
    return (fixture_path / filename).read_text(encoding="utf-8")


def _read_json(fixture_path: Path, filename: str) -> dict[str, Any]:
    payload = json.loads(_read_text(fixture_path, filename))
    if not isinstance(payload, dict):
        msg = f"Fixture does not contain a JSON object: {filename}"
        raise ValueError(msg)
    return payload
