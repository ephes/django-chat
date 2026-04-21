"""Read-only parsers for public Django Chat source data fixtures."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any, Literal
from xml.etree import ElementTree

RSS_FEED_URL = "https://feeds.simplecast.com/WpQaX_cs"
SIMPLECAST_PODCAST_ID = "19d48b52-7d9d-4294-8dbf-7f2739ba2e91"
SIMPLECAST_PODCAST_URL = f"https://api.simplecast.com/podcasts/{SIMPLECAST_PODCAST_ID}"
SIMPLECAST_EPISODES_URL = f"{SIMPLECAST_PODCAST_URL}/episodes"
SIMPLECAST_EPISODE_URL_PREFIX = "https://api.simplecast.com/episodes"
SIMPLECAST_DISTRIBUTION_CHANNELS_URL = f"{SIMPLECAST_PODCAST_URL}/distribution_channels"

RSS_NAMESPACES = {
    "atom": "http://www.w3.org/2005/Atom",
    "content": "http://purl.org/rss/1.0/modules/content/",
    "itunes": "http://www.itunes.com/dtds/podcast-1.0.dtd",
}

JsonObject = dict[str, Any]


@dataclass(frozen=True)
class RssEnclosure:
    """Audio enclosure details from an RSS item."""

    url: str
    media_type: str | None
    length: int | None


@dataclass(frozen=True)
class RssEpisode:
    """Episode fields available from the canonical RSS feed."""

    source_url: str
    guid: str
    guid_is_permalink: bool
    title: str
    published_at: datetime | None
    description_html: str | None
    content_html: str | None
    author: str | None
    link: str | None
    duration_seconds: int | None
    episode_number: int | None
    episode_type: str | None
    explicit: bool | None
    enclosure: RssEnclosure | None


@dataclass(frozen=True)
class RssPodcast:
    """Podcast-level metadata plus RSS item data."""

    source_url: str
    title: str
    description: str | None
    website_url: str | None
    feed_url: str | None
    generator: str | None
    language: str | None
    copyright: str | None
    author: str | None
    owner_name: str | None
    owner_email: str | None
    image_url: str | None
    categories: tuple[str, ...]
    explicit: bool | None
    keywords: tuple[str, ...]
    published_at: datetime | None
    last_build_at: datetime | None
    episodes: tuple[RssEpisode, ...]


@dataclass(frozen=True)
class SimplecastPodcast:
    """Podcast metadata from the unauthenticated Simplecast podcast endpoint."""

    source_url: str
    id: str
    title: str
    description: str | None
    language: str | None
    feed_url: str | None
    website_url: str | None
    image_url: str | None
    status: str | None
    is_explicit: bool | None
    episode_count: int | None
    author_names: tuple[str, ...]
    site_id: str | None
    site_api_url: str | None
    distribution_channels_url: str | None
    published_at: datetime | None
    updated_at: datetime | None


@dataclass(frozen=True)
class SimplecastEpisode:
    """Episode fields from Simplecast list or detail endpoint payloads."""

    source_kind: Literal["list", "detail"]
    source_url: str
    api_url: str | None
    id: str
    guid: str | None
    slug: str | None
    title: str
    episode_number: int | None
    season_number: int | None
    published_at: datetime | None
    updated_at: datetime | None
    description: str | None
    long_description_html: str | None
    transcript_html: str | None
    duration_seconds: int | None
    enclosure_url: str | None
    audio_file_url: str | None
    audio_file_size: int | None
    episode_url: str | None
    status: str | None
    is_hidden: bool | None
    is_explicit: bool | None


@dataclass(frozen=True)
class SimplecastEpisodePage:
    """A paginated Simplecast episode-list response."""

    source_url: str
    count: int | None
    page_total: int | None
    page_current: int | None
    page_limit: int | None
    next_url: str | None
    previous_url: str | None
    episodes: tuple[SimplecastEpisode, ...]


@dataclass(frozen=True)
class SourceLink:
    """A normalized menu, social, or distribution link."""

    source: Literal["simplecast_site", "simplecast_distribution"]
    location: Literal["menu", "social", "distribution"]
    source_id: str | None
    source_url: str | None
    name: str
    url: str
    order: int | None
    new_window: bool | None
    is_visible: bool | None
    channel_id: str | None = None
    channel_name: str | None = None


@dataclass(frozen=True)
class SimplecastSite:
    """Site configuration and public link data from the Simplecast site endpoint."""

    source_url: str
    id: str
    podcast_id: str | None
    url: str | None
    external_website: str | None
    cname_url: str | None
    theme: str | None
    color: str | None
    privacy_policy_link: str | None
    privacy_policy_text: str | None
    legacy_hosts: Any | None
    menu_links: tuple[SourceLink, ...]
    social_links: tuple[SourceLink, ...]


@dataclass(frozen=True)
class EpisodeSourceData:
    """RSS data optionally joined to richer Simplecast endpoint data."""

    matching_key: str
    title: str
    published_at: datetime | None
    rss_guid: str | None
    simplecast_episode_id: str | None
    slug: str | None
    episode_number: int | None
    rss_enclosure_url: str | None
    simplecast_enclosure_url: str | None
    rss: RssEpisode | None
    simplecast: SimplecastEpisode | None


def parse_rss_feed(xml_text: str, *, source_url: str = RSS_FEED_URL) -> RssPodcast:
    """Parse the canonical RSS feed into read-only source structures."""

    root = ElementTree.fromstring(xml_text)
    channel = root.find("channel")
    if channel is None:
        msg = "RSS feed does not contain a channel element."
        raise ValueError(msg)

    feed_url = None
    for atom_link in channel.findall("atom:link", RSS_NAMESPACES):
        if atom_link.attrib.get("rel") == "self":
            feed_url = atom_link.attrib.get("href")
            break

    image = channel.find("image")
    image_url = _text(image, "url") if image is not None else None

    episodes = tuple(
        _parse_rss_episode(item, source_url=source_url) for item in channel.findall("item")
    )

    return RssPodcast(
        source_url=source_url,
        title=_required_text(channel, "title"),
        description=_text(channel, "description"),
        website_url=_text(channel, "link"),
        feed_url=feed_url,
        generator=_text(channel, "generator"),
        language=_text(channel, "language"),
        copyright=_text(channel, "copyright"),
        author=_text(channel, "itunes:author"),
        owner_name=_text(channel, "itunes:owner/itunes:name"),
        owner_email=_text(channel, "itunes:owner/itunes:email"),
        image_url=_itunes_image_url(channel) or image_url,
        categories=tuple(
            category.attrib["text"]
            for category in channel.findall("itunes:category", RSS_NAMESPACES)
            if category.attrib.get("text")
        ),
        explicit=_parse_bool(_text(channel, "itunes:explicit")),
        keywords=_parse_keywords(_text(channel, "itunes:keywords")),
        published_at=_parse_rss_datetime(_text(channel, "pubDate")),
        last_build_at=_parse_rss_datetime(_text(channel, "lastBuildDate")),
        episodes=episodes,
    )


def parse_simplecast_podcast(
    payload: JsonObject,
    *,
    source_url: str | None = None,
) -> SimplecastPodcast:
    """Parse the Simplecast podcast endpoint into normalized metadata."""

    site = _optional_object(payload.get("site"))
    episodes = _optional_object(payload.get("episodes"))
    authors = _optional_object(payload.get("authors"))
    distribution_channels = _optional_object(payload.get("distribution_channels"))

    return SimplecastPodcast(
        source_url=source_url or _optional_str(payload.get("href")) or SIMPLECAST_PODCAST_URL,
        id=_required_str(payload, "id"),
        title=_required_str(payload, "title"),
        description=_optional_str(payload.get("description")),
        language=_optional_str(payload.get("language")),
        feed_url=_optional_str(payload.get("feed_url")),
        website_url=_optional_str(site.get("external_website")),
        image_url=_optional_str(payload.get("image_url")),
        status=_optional_str(payload.get("status")),
        is_explicit=_optional_bool(payload.get("is_explicit")),
        episode_count=_optional_int(episodes.get("count")),
        author_names=tuple(
            author["name"]
            for author in _optional_collection(authors)
            if isinstance(author.get("name"), str)
        ),
        site_id=_optional_str(site.get("id")),
        site_api_url=_optional_str(site.get("href")),
        distribution_channels_url=_optional_str(distribution_channels.get("href")),
        published_at=_parse_iso_datetime(_optional_str(payload.get("published_at"))),
        updated_at=_parse_iso_datetime(_optional_str(payload.get("updated_at"))),
    )


def parse_simplecast_episode_page(
    payload: JsonObject,
    *,
    source_url: str | None = None,
) -> SimplecastEpisodePage:
    """Parse one Simplecast episode-list page."""

    page_source_url = source_url or _optional_str(payload.get("href")) or SIMPLECAST_EPISODES_URL
    pages = _optional_object(payload.get("pages"))
    next_page = _optional_object(pages.get("next"))
    previous_page = _optional_object(pages.get("previous"))

    return SimplecastEpisodePage(
        source_url=page_source_url,
        count=_optional_int(payload.get("count")),
        page_total=_optional_int(pages.get("total")),
        page_current=_optional_int(pages.get("current")),
        page_limit=_optional_int(pages.get("limit")),
        next_url=_optional_str(next_page.get("href")),
        previous_url=_optional_str(previous_page.get("href")),
        episodes=tuple(
            _parse_simplecast_episode(item, source_kind="list", source_url=page_source_url)
            for item in _optional_collection(payload)
        ),
    )


def parse_simplecast_episode_detail(
    payload: JsonObject,
    *,
    source_url: str | None = None,
) -> SimplecastEpisode:
    """Parse a Simplecast per-episode detail object."""

    return _parse_simplecast_episode(
        payload,
        source_kind="detail",
        source_url=_simplecast_episode_source_url(payload, source_url=source_url),
    )


def parse_simplecast_site(
    payload: JsonObject,
    *,
    source_url: str | None = None,
) -> SimplecastSite:
    """Parse Simplecast site configuration, including menu and social links."""

    site_source_url = source_url or _optional_str(payload.get("href")) or ""
    podcast = _optional_object(payload.get("podcast"))

    return SimplecastSite(
        source_url=site_source_url,
        id=_required_str(payload, "id"),
        podcast_id=_optional_str(podcast.get("id")),
        url=_optional_str(payload.get("url")),
        external_website=_optional_str(payload.get("external_website")),
        cname_url=_optional_str(payload.get("cname_url")),
        theme=_optional_str(payload.get("theme")),
        color=_optional_str(payload.get("color")),
        privacy_policy_link=_optional_str(payload.get("privacy_policy_link")),
        privacy_policy_text=_optional_str(payload.get("privacy_policy_text")),
        legacy_hosts=payload.get("legacy_hosts"),
        menu_links=_parse_site_links(payload.get("menu_links"), "menu"),
        social_links=_parse_site_links(payload.get("site_links"), "social"),
    )


def parse_simplecast_distribution_links(
    payload: JsonObject,
) -> tuple[SourceLink, ...]:
    """Parse Simplecast podcast distribution-channel links."""

    links: list[SourceLink] = []
    for item in _optional_collection(payload):
        channel = _optional_object(item.get("distribution_channel"))
        name = _optional_str(channel.get("name"))
        url = _optional_str(item.get("url"))
        if not name or not url:
            continue
        links.append(
            SourceLink(
                source="simplecast_distribution",
                location="distribution",
                source_id=_optional_str(item.get("id")),
                source_url=_optional_str(item.get("href")),
                name=name,
                url=url.strip(),
                order=None,
                new_window=None,
                is_visible=True,
                channel_id=_optional_str(channel.get("id")),
                channel_name=name,
            )
        )
    return tuple(links)


def merge_episode_sources(
    rss_episodes: tuple[RssEpisode, ...],
    simplecast_episodes: tuple[SimplecastEpisode, ...] = (),
) -> tuple[EpisodeSourceData, ...]:
    """Join RSS and Simplecast episodes while preserving the source-specific data."""

    simplecast_by_key: dict[str, SimplecastEpisode] = {}
    for episode in simplecast_episodes:
        for key in _simplecast_match_keys(episode):
            simplecast_by_key.setdefault(key, episode)

    merged: list[EpisodeSourceData] = []
    matched_simplecast_ids: set[str] = set()
    for rss_episode in rss_episodes:
        key = _rss_match_keys(rss_episode)[0]
        simplecast_episode = None
        for candidate_key in _rss_match_keys(rss_episode):
            simplecast_episode = simplecast_by_key.get(candidate_key)
            if simplecast_episode is not None:
                matched_simplecast_ids.add(simplecast_episode.id)
                break
        merged.append(_merged_episode(key, rss_episode, simplecast_episode))

    for simplecast_episode in simplecast_episodes:
        if simplecast_episode.id in matched_simplecast_ids:
            continue
        key = _simplecast_match_keys(simplecast_episode)[0]
        merged.append(_merged_episode(key, None, simplecast_episode))

    return tuple(merged)


def _parse_rss_episode(item: ElementTree.Element, *, source_url: str) -> RssEpisode:
    guid = item.find("guid")
    enclosure = item.find("enclosure")

    return RssEpisode(
        source_url=source_url,
        guid=_required_text(item, "guid"),
        guid_is_permalink=(guid is not None and guid.attrib.get("isPermaLink") == "true"),
        title=_required_text(item, "title"),
        published_at=_parse_rss_datetime(_text(item, "pubDate")),
        description_html=_text(item, "description"),
        content_html=_text(item, "content:encoded"),
        author=_text(item, "author"),
        link=_text(item, "link"),
        duration_seconds=_parse_duration(_text(item, "itunes:duration")),
        episode_number=_parse_int(_text(item, "itunes:episode")),
        episode_type=_text(item, "itunes:episodeType"),
        explicit=_parse_bool(_text(item, "itunes:explicit")),
        enclosure=(
            RssEnclosure(
                url=enclosure.attrib["url"],
                media_type=enclosure.attrib.get("type"),
                length=_parse_int(enclosure.attrib.get("length")),
            )
            if enclosure is not None and enclosure.attrib.get("url")
            else None
        ),
    )


def _parse_simplecast_episode(
    item: JsonObject,
    *,
    source_kind: Literal["list", "detail"],
    source_url: str,
) -> SimplecastEpisode:
    season = _optional_object(item.get("season"))

    return SimplecastEpisode(
        source_kind=source_kind,
        source_url=source_url,
        api_url=_optional_str(item.get("href")),
        id=_required_str(item, "id"),
        guid=_optional_str(item.get("guid")),
        slug=_optional_str(item.get("slug")),
        title=_required_str(item, "title"),
        episode_number=_optional_int(item.get("number")),
        season_number=_optional_int(season.get("number")),
        published_at=_parse_iso_datetime(_optional_str(item.get("published_at"))),
        updated_at=_parse_iso_datetime(_optional_str(item.get("updated_at"))),
        description=_optional_str(item.get("description")),
        long_description_html=_optional_str(item.get("long_description")),
        transcript_html=_optional_str(item.get("transcription")),
        duration_seconds=_optional_int(item.get("duration")),
        enclosure_url=_optional_str(item.get("enclosure_url")),
        audio_file_url=_optional_str(item.get("audio_file_url")),
        audio_file_size=_optional_int(item.get("audio_file_size")),
        episode_url=_optional_str(item.get("episode_url")),
        status=_optional_str(item.get("status")),
        is_hidden=_optional_bool(item.get("is_hidden")),
        is_explicit=_optional_bool(item.get("is_explicit")),
    )


def _parse_site_links(
    payload: Any,
    location: Literal["menu", "social"],
) -> tuple[SourceLink, ...]:
    links: list[SourceLink] = []
    for item in _optional_collection(payload):
        name = _optional_str(item.get("name"))
        url = _optional_str(item.get("url"))
        if not name or not url:
            continue
        links.append(
            SourceLink(
                source="simplecast_site",
                location=location,
                source_id=_optional_str(item.get("id")),
                source_url=_optional_str(item.get("href")),
                name=name,
                url=url.strip(),
                order=_optional_int(item.get("order")),
                new_window=_optional_bool(item.get("new_window")),
                is_visible=_optional_bool(item.get("is_visible")),
            )
        )
    return tuple(sorted(links, key=lambda link: (link.order is None, link.order or 0, link.name)))


def _merged_episode(
    matching_key: str,
    rss_episode: RssEpisode | None,
    simplecast_episode: SimplecastEpisode | None,
) -> EpisodeSourceData:
    rss_enclosure_url = rss_episode.enclosure.url if rss_episode and rss_episode.enclosure else None

    return EpisodeSourceData(
        matching_key=matching_key,
        title=(
            simplecast_episode.title
            if simplecast_episode
            else rss_episode.title
            if rss_episode
            else ""
        ),
        published_at=simplecast_episode.published_at
        if simplecast_episode and simplecast_episode.published_at
        else rss_episode.published_at
        if rss_episode
        else None,
        rss_guid=rss_episode.guid if rss_episode else None,
        simplecast_episode_id=simplecast_episode.id if simplecast_episode else None,
        slug=simplecast_episode.slug if simplecast_episode else None,
        episode_number=(
            simplecast_episode.episode_number
            if simplecast_episode and simplecast_episode.episode_number is not None
            else rss_episode.episode_number
            if rss_episode
            else None
        ),
        rss_enclosure_url=rss_enclosure_url,
        simplecast_enclosure_url=simplecast_episode.enclosure_url if simplecast_episode else None,
        rss=rss_episode,
        simplecast=simplecast_episode,
    )


def _rss_match_keys(episode: RssEpisode) -> tuple[str, ...]:
    keys: list[str] = []
    if episode.guid:
        keys.append(f"guid:{episode.guid}")
    if episode.episode_number is not None:
        keys.append(f"episode-number:{episode.episode_number}")
    keys.append(f"title:{episode.title}")
    return tuple(keys)


def _simplecast_match_keys(episode: SimplecastEpisode) -> tuple[str, ...]:
    keys: list[str] = []
    if episode.guid:
        keys.append(f"guid:{episode.guid}")
    if episode.episode_number is not None:
        keys.append(f"episode-number:{episode.episode_number}")
    if episode.slug:
        keys.append(f"slug:{episode.slug}")
    keys.append(f"simplecast-id:{episode.id}")
    return tuple(keys)


def _simplecast_episode_source_url(payload: JsonObject, *, source_url: str | None) -> str:
    explicit_url = source_url or _optional_str(payload.get("href"))
    if explicit_url:
        return explicit_url
    episode_id = _optional_str(payload.get("id"))
    if episode_id:
        return f"{SIMPLECAST_EPISODE_URL_PREFIX}/{episode_id}"
    return ""


def _text(element: ElementTree.Element | None, path: str) -> str | None:
    if element is None:
        return None
    child = element.find(path, RSS_NAMESPACES)
    if child is None or child.text is None:
        return None
    text = child.text.strip()
    return text or None


def _required_text(element: ElementTree.Element, path: str) -> str:
    text = _text(element, path)
    if text is None:
        msg = f"Required RSS element is missing: {path}"
        raise ValueError(msg)
    return text


def _itunes_image_url(element: ElementTree.Element) -> str | None:
    image = element.find("itunes:image", RSS_NAMESPACES)
    if image is None:
        return None
    return image.attrib.get("href")


def _parse_rss_datetime(value: str | None) -> datetime | None:
    if value is None:
        return None
    parsed = parsedate_to_datetime(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _parse_iso_datetime(value: str | None) -> datetime | None:
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _parse_duration(value: str | None) -> int | None:
    if value is None:
        return None
    if value.isdigit():
        return int(value)

    parts = value.split(":")
    if not all(part.isdigit() for part in parts):
        return None
    seconds = 0
    for part in parts:
        seconds = seconds * 60 + int(part)
    return seconds


def _parse_bool(value: str | None) -> bool | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    if normalized in {"true", "yes", "1"}:
        return True
    if normalized in {"false", "no", "0"}:
        return False
    return None


def _parse_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _parse_keywords(value: str | None) -> tuple[str, ...]:
    if value is None:
        return ()
    return tuple(keyword.strip() for keyword in value.split(",") if keyword.strip())


def _optional_object(value: Any) -> JsonObject:
    return value if isinstance(value, dict) else {}


def _optional_collection(payload: Any) -> tuple[JsonObject, ...]:
    if not isinstance(payload, dict):
        return ()
    collection = payload.get("collection")
    if not isinstance(collection, list):
        return ()
    return tuple(item for item in collection if isinstance(item, dict))


def _required_str(payload: JsonObject, key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        msg = f"Required Simplecast string field is missing: {key}"
        raise ValueError(msg)
    return value


def _optional_str(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _optional_bool(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


def _optional_int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None
