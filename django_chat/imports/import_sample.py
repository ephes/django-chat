from __future__ import annotations

import hashlib
import json
import mimetypes
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any, cast
from urllib.parse import unquote, urlparse
from urllib.request import Request, urlopen

from cast.models import Audio, Episode, Podcast
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.html import strip_tags
from django.utils.text import slugify
from wagtail.models import Page, Site

from django_chat.imports.models import (
    EpisodeAudioImportMetadata,
    EpisodeSourceMetadata,
    PodcastSourceLink,
    PodcastSourceMetadata,
)
from django_chat.imports.source_data import (
    EpisodeSourceData,
    RssPodcast,
    SimplecastEpisode,
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

DEFAULT_SOURCE_FIXTURE_DIR = Path(__file__).parent / "tests" / "fixtures" / "django_chat_source"
PODCAST_PAGE_SLUG = "episodes"

DETAIL_FIXTURE_FILENAMES = (
    "simplecast_episode_detail_0_preview.json",
    "simplecast_episode_detail_1_what-is-django.json",
    "simplecast_episode_detail_2_how-to-learn-django.json",
    "simplecast_episode_detail_200_django-tasks-jake-howard.json",
)
IMPORT_AUDIO_USERNAME = "django-chat-importer"

AudioDownloader = Callable[[str], "DownloadedAudio"]


@dataclass(frozen=True)
class SampleSourceData:
    rss_podcast: RssPodcast
    simplecast_podcast: SimplecastPodcast
    simplecast_site: SimplecastSite
    source_links: tuple[SourceLink, ...]
    episodes: tuple[EpisodeSourceData, ...]


@dataclass(frozen=True)
class SampleImportResult:
    podcast: Podcast
    podcast_metadata: PodcastSourceMetadata
    source_links: tuple[PodcastSourceLink, ...]
    episodes: tuple[Episode, ...]
    episode_metadata: tuple[EpisodeSourceMetadata, ...]
    audio_metadata: tuple[EpisodeAudioImportMetadata, ...]
    podcast_created: bool
    episodes_created: int
    audio_created: int
    audio_copied: int


@dataclass(frozen=True)
class DownloadedAudio:
    content: bytes
    content_type: str | None = None
    content_length: int | None = None
    filename: str | None = None


@dataclass(frozen=True)
class AudioSourceSelection:
    url: str
    kind: str


@dataclass(frozen=True)
class AudioCopyResult:
    audio_metadata: EpisodeAudioImportMetadata
    audio: Audio
    audio_created: bool
    file_copied: bool


def load_sample_source_data(
    fixture_dir: Path | str = DEFAULT_SOURCE_FIXTURE_DIR,
) -> SampleSourceData:
    fixture_path = Path(fixture_dir)
    rss_podcast = parse_rss_feed(_read_text(fixture_path, "rss_feed.xml"))
    simplecast_podcast = parse_simplecast_podcast(
        _read_json(fixture_path, "simplecast_podcast.json")
    )
    simplecast_site = parse_simplecast_site(_read_json(fixture_path, "simplecast_site.json"))
    distribution_links = parse_simplecast_distribution_links(
        _read_json(fixture_path, "simplecast_distribution_channels.json")
    )
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
        source_links=(
            *simplecast_site.menu_links,
            *simplecast_site.social_links,
            *distribution_links,
        ),
        episodes=merge_episode_sources(rss_podcast.episodes, simplecast_episodes),
    )


def import_django_chat_sample(
    fixture_dir: Path | str = DEFAULT_SOURCE_FIXTURE_DIR,
    *,
    copy_audio: bool = False,
    audio_downloader: AudioDownloader | None = None,
) -> SampleImportResult:
    source_data = load_sample_source_data(fixture_dir)
    with transaction.atomic():
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
        source_links = _update_podcast_source_links(podcast_metadata, source_data.source_links)

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

    audio_results = (
        copy_django_chat_sample_audio(tuple(episode_metadata), audio_downloader=audio_downloader)
        if copy_audio
        else ()
    )

    return SampleImportResult(
        podcast=podcast,
        podcast_metadata=podcast_metadata,
        source_links=source_links,
        episodes=tuple(episodes),
        episode_metadata=tuple(episode_metadata),
        audio_metadata=tuple(result.audio_metadata for result in audio_results),
        podcast_created=podcast_created,
        episodes_created=episodes_created,
        audio_created=sum(1 for result in audio_results if result.audio_created),
        audio_copied=sum(1 for result in audio_results if result.file_copied),
    )


def copy_django_chat_sample_audio(
    episode_metadata: tuple[EpisodeSourceMetadata, ...],
    *,
    audio_downloader: AudioDownloader | None = None,
) -> tuple[AudioCopyResult, ...]:
    """Copy fixture-sample audio for source metadata rows that expose source URLs."""

    downloader = audio_downloader or default_download_audio
    results: list[AudioCopyResult] = []
    for metadata in episode_metadata:
        results.append(_copy_episode_audio(metadata, downloader))
    return tuple(results)


def default_download_audio(source_url: str) -> DownloadedAudio:
    request = Request(source_url, headers={"User-Agent": "django-chat-sample-import/1.0"})
    with urlopen(request, timeout=60) as response:
        content = response.read()
        headers = response.headers
        content_type = headers.get_content_type() if hasattr(headers, "get_content_type") else None
        content_length = _optional_positive_int(headers.get("Content-Length"))

    return DownloadedAudio(
        content=content,
        content_type=content_type,
        content_length=content_length,
        filename=_source_url_filename(source_url),
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
    if page.owner_id is None:
        page.owner = _get_import_user()
    page.author = _join_text(simplecast_podcast.author_names) or rss_podcast.author
    page.email = rss_podcast.owner_email
    page.subtitle = _truncate(strip_tags(description), 255)
    page.description = description
    page.search_description = strip_tags(description)
    page.comments_enabled = False
    page.template_base_dir = "django_chat"
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


def _update_podcast_source_links(
    podcast_metadata: PodcastSourceMetadata,
    source_links: tuple[SourceLink, ...],
) -> tuple[PodcastSourceLink, ...]:
    imported_links: list[PodcastSourceLink] = []
    source_keys: list[str] = []
    for index, source_link in enumerate(source_links):
        source_key = _source_link_key(source_link)
        source_keys.append(source_key)
        link, _ = PodcastSourceLink.objects.update_or_create(
            podcast_metadata=podcast_metadata,
            source_key=source_key,
            defaults={
                "source": source_link.source,
                "location": source_link.location,
                "source_id": source_link.source_id or "",
                "source_url": source_link.source_url or "",
                "name": source_link.name,
                "url": source_link.url,
                "display_order": (
                    source_link.order if source_link.order is not None else index * 100
                ),
                "new_window": source_link.new_window,
                "is_visible": source_link.is_visible is not False,
                "channel_id": source_link.channel_id or "",
                "channel_name": source_link.channel_name or "",
            },
        )
        imported_links.append(link)

    cast(Any, podcast_metadata).source_links.exclude(source_key__in=source_keys).delete()
    return tuple(imported_links)


def _source_link_key(source_link: SourceLink) -> str:
    if source_link.source_id:
        identifier = source_link.source_id
    elif source_link.channel_id:
        identifier = source_link.channel_id
    else:
        identifier = hashlib.sha256(f"{source_link.name}\0{source_link.url}".encode()).hexdigest()
    return f"{source_link.source}:{source_link.location}:{identifier}"


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
        msg = (
            "Episode slug collision without matching Django Chat source metadata: "
            f"slug={slug!r}, existing_title={existing.title!r}, "
            f"source_title={episode_source.title!r}. Refusing to adopt an ambiguous page."
        )
        raise RuntimeError(msg)

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
    if page.owner_id is None:
        page.owner = _get_import_user()
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


def _copy_episode_audio(
    metadata: EpisodeSourceMetadata,
    audio_downloader: AudioDownloader,
) -> AudioCopyResult:
    source = _select_audio_source(metadata)
    existing = _existing_audio_metadata(metadata)
    if existing is not None and _existing_audio_matches_source(existing, source):
        existing_audio = cast(Audio, existing.audio)
        _update_audio_record(existing_audio, metadata, source)
        _attach_episode_audio(metadata, existing_audio)
        return AudioCopyResult(
            audio_metadata=existing,
            audio=existing_audio,
            audio_created=False,
            file_copied=False,
        )

    downloaded = audio_downloader(source.url)
    if not downloaded.content:
        msg = f"Audio source returned no content: {source.url}"
        raise ValueError(msg)

    with transaction.atomic():
        metadata = (
            EpisodeSourceMetadata.objects.select_related("episode")
            .select_for_update()
            .get(pk=metadata.pk)
        )
        existing = _existing_audio_metadata(metadata)
        audio = (
            cast(Audio, existing.audio) if existing is not None else Audio(user=_get_import_user())
        )
        audio_created = audio.pk is None
        _update_audio_record(audio, metadata, source, downloaded=downloaded)
        source_byte_size = _metadata_audio_file_size(metadata)
        if source_byte_size is None:
            source_byte_size = downloaded.content_length
        audio_import_metadata, _ = EpisodeAudioImportMetadata.objects.update_or_create(
            episode_metadata=metadata,
            defaults={
                "audio": audio,
                "source_url": source.url,
                "source_url_kind": source.kind,
                "source_content_type": _audio_content_type(downloaded),
                "source_byte_size": source_byte_size,
                "copied_byte_size": len(downloaded.content),
                "storage_name": cast(Any, audio).mp3.name,
                "copied_at": timezone.now(),
            },
        )
        _attach_episode_audio(metadata, audio)

    return AudioCopyResult(
        audio_metadata=audio_import_metadata,
        audio=audio,
        audio_created=audio_created,
        file_copied=True,
    )


def _existing_audio_metadata(
    metadata: EpisodeSourceMetadata,
) -> EpisodeAudioImportMetadata | None:
    return (
        EpisodeAudioImportMetadata.objects.select_related("audio", "episode_metadata__episode")
        .filter(episode_metadata=metadata)
        .first()
    )


def _existing_audio_matches_source(
    audio_metadata: EpisodeAudioImportMetadata,
    source: AudioSourceSelection,
) -> bool:
    audio_file = cast(Any, audio_metadata.audio).mp3
    storage_name = cast(str, audio_metadata.storage_name)
    return (
        audio_metadata.source_url == source.url
        and bool(storage_name)
        and audio_file.name == storage_name
        and audio_file.storage.exists(audio_file.name)
    )


def _select_audio_source(metadata: EpisodeSourceMetadata) -> AudioSourceSelection:
    if metadata.simplecast_audio_file_url:
        return AudioSourceSelection(
            url=cast(str, metadata.simplecast_audio_file_url),
            kind="simplecast_audio_file_url",
        )
    if metadata.simplecast_enclosure_url:
        return AudioSourceSelection(
            url=cast(str, metadata.simplecast_enclosure_url),
            kind="simplecast_enclosure_url",
        )
    if metadata.original_rss_enclosure_url:
        return AudioSourceSelection(
            url=cast(str, metadata.original_rss_enclosure_url),
            kind="rss_enclosure_url",
        )
    msg = f"Episode metadata has no audio source URL: {metadata.matching_key}"
    raise ValueError(msg)


def _update_audio_record(
    audio: Audio,
    metadata: EpisodeSourceMetadata,
    source: AudioSourceSelection,
    *,
    downloaded: DownloadedAudio | None = None,
) -> None:
    audio_fields = cast(Any, audio)
    desired_user = audio_fields.user if audio_fields.user_id else _get_import_user()
    desired_title = cast(str, metadata.source_title)
    desired_subtitle = _audio_subtitle(metadata)
    desired_duration = None
    duration_seconds = _metadata_duration_seconds(metadata)
    if duration_seconds is not None:
        desired_duration = timedelta(seconds=duration_seconds)
    desired_data = _audio_data(audio, metadata, source, downloaded=downloaded)

    needs_save = False
    if audio_fields.user_id != desired_user.pk:
        audio_fields.user = desired_user
        needs_save = True
    if audio_fields.title != desired_title:
        audio_fields.title = desired_title
        needs_save = True
    if audio_fields.subtitle != desired_subtitle:
        audio_fields.subtitle = desired_subtitle
        needs_save = True
    if audio_fields.duration != desired_duration:
        audio_fields.duration = desired_duration
        needs_save = True
    if audio_fields.data != desired_data:
        audio_fields.data = desired_data
        needs_save = True
    if downloaded is not None:
        audio_fields.mp3.save(
            _destination_audio_filename(metadata, downloaded),
            ContentFile(downloaded.content),
            save=False,
        )
        needs_save = True
    if needs_save:
        audio.save(duration=False, cache_file_sizes=False)


def _attach_episode_audio(metadata: EpisodeSourceMetadata, audio: Audio) -> None:
    episode = cast(Episode, metadata.episode)
    episode_fields = cast(Any, episode)
    if episode_fields.podcast_audio_id == audio.pk:
        return
    Episode.objects.filter(pk=episode.pk).update(podcast_audio=audio)
    episode_fields.podcast_audio = audio


def _audio_data(
    audio: Audio,
    metadata: EpisodeSourceMetadata,
    source: AudioSourceSelection,
    *,
    downloaded: DownloadedAudio | None,
) -> dict[str, Any]:
    data = dict(cast(Any, audio).data or {})
    data["django_chat_source"] = {
        "matching_key": metadata.matching_key,
        "source_url": source.url,
        "source_url_kind": source.kind,
    }
    byte_size = len(downloaded.content) if downloaded is not None else None
    if byte_size is not None:
        sizes = dict(data.get("size") or {})
        sizes["mp3"] = byte_size
        data["size"] = sizes
    return data


def _audio_subtitle(metadata: EpisodeSourceMetadata) -> str:
    episode_number = cast(int | None, metadata.episode_number)
    if episode_number is None:
        return ""
    return f"Episode {episode_number}"


def _destination_audio_filename(
    metadata: EpisodeSourceMetadata,
    downloaded: DownloadedAudio,
) -> str:
    slug = (
        cast(str, metadata.simplecast_slug)
        or slugify(cast(str, metadata.source_title))
        or "episode"
    )
    slug = slug[:48].strip("-") or "episode"
    identifier = (
        cast(str, metadata.simplecast_episode_id)
        or cast(str, metadata.rss_guid)
        or cast(str, metadata.matching_key)
        or cast(str, metadata.source_title)
    )
    digest = hashlib.sha256(identifier.encode()).hexdigest()[:12]
    extension = _audio_extension(downloaded)
    return f"django-chat-sample/{slug}-{digest}{extension}"


def _metadata_audio_file_size(metadata: EpisodeSourceMetadata) -> int | None:
    return cast(int | None, metadata.audio_file_size)


def _metadata_duration_seconds(metadata: EpisodeSourceMetadata) -> int | None:
    return cast(int | None, metadata.duration_seconds)


def _audio_extension(downloaded: DownloadedAudio) -> str:
    source_filename = downloaded.filename or ""
    suffix = Path(source_filename).suffix.lower()
    if suffix in {".mp3", ".m4a", ".oga", ".opus"}:
        return suffix
    guessed = mimetypes.guess_extension(downloaded.content_type or "")
    return guessed if guessed in {".mp3", ".m4a", ".oga", ".opus"} else ".mp3"


def _audio_content_type(downloaded: DownloadedAudio) -> str:
    if downloaded.content_type:
        return downloaded.content_type[:255]
    guessed_type, _ = mimetypes.guess_type(downloaded.filename or "")
    return (guessed_type or "audio/mpeg")[:255]


def _source_url_filename(source_url: str) -> str:
    return Path(unquote(urlparse(source_url).path)).name


def _optional_positive_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        parsed = int(value)
    except ValueError:
        return None
    return parsed if parsed >= 0 else None


def _get_import_user() -> Any:
    user_model = get_user_model()
    existing = user_model._default_manager.filter(username=IMPORT_AUDIO_USERNAME).first()
    if existing is not None:
        return existing

    user = user_model(username=IMPORT_AUDIO_USERNAME, email="")
    user.set_unusable_password()
    user.save()
    return user


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
