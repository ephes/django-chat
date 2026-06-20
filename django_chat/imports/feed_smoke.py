from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Literal
from xml.etree import ElementTree

from django.conf import settings
from django.core.cache import cache
from django.test import Client
from django.urls import reverse

from django_chat.imports.import_sample import DEFAULT_SOURCE_FIXTURE_DIR
from django_chat.imports.models import EpisodeSourceMetadata
from django_chat.imports.source_data import (
    RSS_NAMESPACES,
    VALID_EPISODE_TYPES,
    RssEpisode,
    RssPodcast,
    parse_rss_feed,
)

Severity = Literal["failure", "warning"]
PODCAST_NAMESPACE = "https://podcastindex.org/namespace/1.0/"
GENERATED_FEED_NAMESPACES = RSS_NAMESPACES | {"podcast": PODCAST_NAMESPACE}


@dataclass(frozen=True)
class FeedSmokeMessage:
    severity: Severity
    text: str


@dataclass(frozen=True)
class FeedSmokeEnclosure:
    url: str
    media_type: str | None
    length: int | None


@dataclass(frozen=True)
class GeneratedFeedItem:
    guid: str | None
    title: str
    published_at: datetime | None
    duration_seconds: int | None
    episode_number: int | None
    podcast_episode_number: int | None
    episode_type: str | None
    season_number: int | None
    podcast_season_number: int | None
    keywords: str | None
    enclosure: FeedSmokeEnclosure | None


@dataclass(frozen=True)
class GeneratedPodcastFeed:
    title: str
    link: str | None
    self_url: str | None
    items: tuple[GeneratedFeedItem, ...]


@dataclass(frozen=True)
class FeedSmokeResult:
    source_feed_url: str
    generated_feed_path: str
    source_item_count: int
    generated_item_count: int
    messages: tuple[FeedSmokeMessage, ...]

    @property
    def failures(self) -> tuple[FeedSmokeMessage, ...]:
        return tuple(message for message in self.messages if message.severity == "failure")

    @property
    def warnings(self) -> tuple[FeedSmokeMessage, ...]:
        return tuple(message for message in self.messages if message.severity == "warning")

    @property
    def passed(self) -> bool:
        return not self.failures


def compare_django_chat_sample_feed(
    fixture_dir: Path | str = DEFAULT_SOURCE_FIXTURE_DIR,
    *,
    podcast_slug: str | None = None,
    audio_format: str = "mp3",
    host: str = "localhost",
) -> FeedSmokeResult:
    """Compare the local generated django-cast podcast feed to the sample RSS fixture."""

    podcast_slug = podcast_slug or settings.DJANGO_CHAT_PODCAST_SLUG
    source = load_source_feed(fixture_dir)
    feed_path = reverse("cast:podcast_feed_rss", args=[podcast_slug, audio_format])
    response = fetch_generated_feed(feed_path, host=host)
    if response.status_code != 200:
        next_step = ""
        if response.status_code == 404:
            next_step = (
                " Run `just manage migrate` and `just manage import_django_chat_sample "
                "--copy-audio` before comparing."
            )
        return FeedSmokeResult(
            source_feed_url=source.feed_url or source.source_url,
            generated_feed_path=feed_path,
            source_item_count=len(source.episodes),
            generated_item_count=0,
            messages=(
                FeedSmokeMessage(
                    "failure",
                    f"Generated feed returned HTTP {response.status_code} for {feed_path}."
                    f"{next_step}",
                ),
            ),
        )

    try:
        generated = parse_generated_podcast_feed(response.content)
    except (ElementTree.ParseError, ValueError) as exc:
        return FeedSmokeResult(
            source_feed_url=source.feed_url or source.source_url,
            generated_feed_path=feed_path,
            source_item_count=len(source.episodes),
            generated_item_count=0,
            messages=(
                FeedSmokeMessage(
                    "failure",
                    f"Generated feed could not be parsed as the expected RSS shape: {exc}.",
                ),
            ),
        )

    return compare_source_to_generated_feed(
        source,
        generated,
        generated_feed_path=feed_path,
    )


def load_source_feed(fixture_dir: Path | str = DEFAULT_SOURCE_FIXTURE_DIR) -> RssPodcast:
    fixture_path = Path(fixture_dir)
    return parse_rss_feed((fixture_path / "rss_feed.xml").read_text())


def fetch_generated_feed(feed_path: str, *, host: str = "localhost"):
    # django-cast feed routes are cached; clear cache so local smoke checks see current imports.
    cache.clear()
    return Client(HTTP_HOST=host).get(feed_path)


def parse_generated_podcast_feed(xml_content: bytes | str) -> GeneratedPodcastFeed:
    root = ElementTree.fromstring(xml_content)
    channel = root.find("channel")
    if channel is None:
        msg = "Generated RSS feed does not contain a channel element."
        raise ValueError(msg)

    items = tuple(_parse_generated_item(item) for item in channel.findall("item"))
    return GeneratedPodcastFeed(
        title=_required_child_text(channel, "title"),
        link=_child_text(channel, "link"),
        self_url=_atom_self_url(channel),
        items=items,
    )


def compare_source_to_generated_feed(
    source: RssPodcast,
    generated: GeneratedPodcastFeed,
    *,
    generated_feed_path: str,
    copied_byte_sizes_by_guid: dict[str, int] | None = None,
    strict_live_parity: bool = False,
) -> FeedSmokeResult:
    """Compare a parsed source feed against a parsed generated/candidate feed.

    With ``strict_live_parity`` enabled the comparison adds the live cutover
    gates from ``docs/feed-cutover-analysis.md`` Phase 2: any candidate GUID
    absent from the source feed fails, any source GUID missing from the
    candidate fails (with a pointed failure when the latest source episode is
    the one missing), and title comparison normalizes whitespace so
    whitespace-only differences pass while real differences still fail. The flag
    defaults off so existing callers keep exact-title semantics unchanged.
    """

    messages: list[FeedSmokeMessage] = []
    source_feed_url = source.feed_url or source.source_url

    _compare_equal(
        messages,
        label="feed title",
        source_value=source.title,
        generated_value=generated.title,
    )

    source_items = source.episodes
    generated_items = generated.items
    if len(generated_items) != len(source_items):
        messages.append(
            FeedSmokeMessage(
                "failure",
                "Generated feed item count mismatch: "
                f"source={len(source_items)}, generated={len(generated_items)}.",
            )
        )
        if not generated_items and source_items:
            messages.append(
                FeedSmokeMessage(
                    "failure",
                    "Generated feed has no items. Run "
                    "`just manage import_django_chat_sample --copy-audio` before comparing; "
                    "django-cast excludes episodes without podcast audio from podcast feeds.",
                )
            )

    source_guid_order = tuple(episode.guid for episode in source_items)
    generated_guid_order = tuple(item.guid for item in generated_items)
    if len(generated_items) == len(source_items) and generated_guid_order != source_guid_order:
        messages.append(
            FeedSmokeMessage(
                "failure",
                "Generated feed GUID order mismatch. Re-run the sample import so imported "
                "episodes use the RSS GUIDs, then compare again.",
            )
        )

    generated_by_guid = {
        item.guid: item for item in generated_items if item.guid is not None and item.guid != ""
    }

    if strict_live_parity:
        _compare_guid_sets(
            messages,
            source_items=source_items,
            generated_by_guid=generated_by_guid,
        )

    source_byte_warnings: list[str] = []
    url_warnings: list[str] = []

    copied_sizes = (
        _copied_byte_sizes_by_guid()
        if copied_byte_sizes_by_guid is None
        else copied_byte_sizes_by_guid
    )
    for source_item in source_items:
        generated_item = generated_by_guid.get(source_item.guid)
        if generated_item is None:
            continue

        item_label = f"{source_item.guid} ({source_item.title})"
        _compare_title(
            messages,
            label=f"{item_label} title",
            source_value=source_item.title,
            generated_value=generated_item.title,
            normalize_whitespace=strict_live_parity,
        )
        _compare_equal(
            messages,
            label=f"{item_label} publication date",
            source_value=source_item.published_at,
            generated_value=generated_item.published_at,
        )
        if source_item.duration_seconds is not None and generated_item.duration_seconds is not None:
            _compare_equal(
                messages,
                label=f"{item_label} duration",
                source_value=source_item.duration_seconds,
                generated_value=generated_item.duration_seconds,
            )
        _compare_episode_number(messages, source_item=source_item, generated_item=generated_item)
        _compare_episode_type(messages, source_item=source_item, generated_item=generated_item)
        _compare_podcast_metadata_consistency(
            messages,
            item_label=item_label,
            generated_item=generated_item,
        )

        _compare_enclosure(
            messages,
            source_item=source_item,
            generated_item=generated_item,
            copied_byte_size=copied_sizes.get(source_item.guid),
            source_byte_warnings=source_byte_warnings,
            url_warnings=url_warnings,
        )

    if url_warnings:
        messages.append(
            FeedSmokeMessage(
                "warning",
                "Generated enclosure URLs differ from the Simplecast fixture for "
                f"{len(url_warnings)} item(s), as expected for copied local/S3 media. "
                f"First difference: {url_warnings[0]}.",
            )
        )
    if source_byte_warnings:
        messages.append(
            FeedSmokeMessage(
                "warning",
                "Generated enclosure lengths differ from Simplecast source-reported bytes for "
                f"{len(source_byte_warnings)} item(s). Strict length checking uses copied bytes. "
                f"First difference: {source_byte_warnings[0]}.",
            )
        )

    return FeedSmokeResult(
        source_feed_url=source_feed_url,
        generated_feed_path=generated_feed_path,
        source_item_count=len(source_items),
        generated_item_count=len(generated_items),
        messages=tuple(messages),
    )


def format_feed_smoke_result(result: FeedSmokeResult) -> str:
    lines = [
        "Django Chat feed smoke check",
        f"Source feed: {result.source_feed_url}",
        f"Generated feed route: {result.generated_feed_path}",
        (
            "Compared items: "
            f"source={result.source_item_count}, generated={result.generated_item_count}"
        ),
    ]
    if result.passed:
        lines.append("PASS strict feed smoke checks passed.")
    else:
        lines.append(f"FAIL strict feed smoke checks found {len(result.failures)} issue(s).")

    for failure in result.failures:
        lines.append(f"FAIL {failure.text}")
    for warning in result.warnings:
        lines.append(f"WARN {warning.text}")
    return "\n".join(lines)


def _compare_episode_number(
    messages: list[FeedSmokeMessage],
    *,
    source_item: RssEpisode,
    generated_item: GeneratedFeedItem,
) -> None:
    item_label = f"{source_item.guid} ({source_item.title})"
    if source_item.episode_number is None:
        return
    if source_item.episode_number <= 0:
        if generated_item.episode_number is not None:
            messages.append(
                FeedSmokeMessage(
                    "failure",
                    f"{item_label} should omit non-positive itunes:episode "
                    f"{source_item.episode_number!r}, but generated "
                    f"{generated_item.episode_number!r}.",
                )
            )
        if generated_item.podcast_episode_number is not None:
            messages.append(
                FeedSmokeMessage(
                    "failure",
                    f"{item_label} should omit non-positive podcast:episode "
                    f"{source_item.episode_number!r}, but generated "
                    f"{generated_item.podcast_episode_number!r}.",
                )
            )
        return

    _compare_equal(
        messages,
        label=f"{item_label} itunes:episode",
        source_value=source_item.episode_number,
        generated_value=generated_item.episode_number,
    )
    _compare_equal(
        messages,
        label=f"{item_label} podcast:episode",
        source_value=source_item.episode_number,
        generated_value=generated_item.podcast_episode_number,
    )


def _compare_episode_type(
    messages: list[FeedSmokeMessage],
    *,
    source_item: RssEpisode,
    generated_item: GeneratedFeedItem,
) -> None:
    if source_item.episode_type is None:
        return
    source_type = source_item.episode_type.strip().lower()
    if source_type not in VALID_EPISODE_TYPES:
        return
    _compare_equal(
        messages,
        label=f"{source_item.guid} ({source_item.title}) itunes:episodeType",
        source_value=source_type,
        generated_value=generated_item.episode_type,
    )


def _compare_podcast_metadata_consistency(
    messages: list[FeedSmokeMessage],
    *,
    item_label: str,
    generated_item: GeneratedFeedItem,
) -> None:
    if generated_item.episode_number != generated_item.podcast_episode_number:
        messages.append(
            FeedSmokeMessage(
                "failure",
                f"{item_label} has inconsistent episode metadata: "
                f"itunes:episode={generated_item.episode_number!r}, "
                f"podcast:episode={generated_item.podcast_episode_number!r}.",
            )
        )
    if generated_item.season_number != generated_item.podcast_season_number:
        messages.append(
            FeedSmokeMessage(
                "failure",
                f"{item_label} has inconsistent season metadata: "
                f"itunes:season={generated_item.season_number!r}, "
                f"podcast:season={generated_item.podcast_season_number!r}.",
            )
        )


def _compare_enclosure(
    messages: list[FeedSmokeMessage],
    *,
    source_item: RssEpisode,
    generated_item: GeneratedFeedItem,
    copied_byte_size: int | None,
    source_byte_warnings: list[str],
    url_warnings: list[str],
) -> None:
    source_enclosure = source_item.enclosure
    generated_enclosure = generated_item.enclosure
    item_label = f"{source_item.guid} ({source_item.title})"
    if source_enclosure is None:
        if generated_enclosure is not None:
            messages.append(
                FeedSmokeMessage(
                    "failure",
                    f"{item_label} has a generated enclosure but none in the source fixture.",
                )
            )
        return
    if generated_enclosure is None:
        messages.append(
            FeedSmokeMessage(
                "failure",
                f"{item_label} is missing a generated enclosure. "
                "Copy sample audio before comparing.",
            )
        )
        return

    _compare_equal(
        messages,
        label=f"{item_label} enclosure type",
        source_value=source_enclosure.media_type,
        generated_value=generated_enclosure.media_type,
    )
    if not generated_enclosure.url:
        messages.append(FeedSmokeMessage("failure", f"{item_label} enclosure URL is empty."))
    elif generated_enclosure.url != source_enclosure.url:
        url_warnings.append(f"{source_item.guid}: generated={generated_enclosure.url}")

    if copied_byte_size is None:
        messages.append(
            FeedSmokeMessage(
                "warning",
                f"{item_label} generated enclosure length could not be checked against copied "
                "bytes because no EpisodeAudioImportMetadata row was found.",
            )
        )
    elif generated_enclosure.length != copied_byte_size:
        messages.append(
            FeedSmokeMessage(
                "failure",
                f"{item_label} enclosure copied length mismatch: "
                f"copied={copied_byte_size}, generated={generated_enclosure.length}.",
            )
        )

    if (
        source_enclosure.length is not None
        and generated_enclosure.length is not None
        and source_enclosure.length != generated_enclosure.length
    ):
        source_byte_warnings.append(
            f"{source_item.guid}: source={source_enclosure.length}, "
            f"generated={generated_enclosure.length}"
        )


def _copied_byte_sizes_by_guid() -> dict[str, int]:
    metadata_rows = (
        EpisodeSourceMetadata.objects.select_related("audio_import_metadata")
        .exclude(rss_guid="")
        .filter(audio_import_metadata__isnull=False)
        .values_list("rss_guid", "audio_import_metadata__copied_byte_size")
    )
    return {guid: copied_size for guid, copied_size in metadata_rows if copied_size is not None}


def _compare_equal(
    messages: list[FeedSmokeMessage],
    *,
    label: str,
    source_value,
    generated_value,
) -> None:
    if source_value != generated_value:
        messages.append(
            FeedSmokeMessage(
                "failure",
                f"{label} mismatch: source={source_value!r}, generated={generated_value!r}.",
            )
        )


def _compare_title(
    messages: list[FeedSmokeMessage],
    *,
    label: str,
    source_value: str,
    generated_value: str,
    normalize_whitespace: bool,
) -> None:
    left = source_value
    right = generated_value
    if normalize_whitespace:
        left = _normalize_whitespace(left)
        right = _normalize_whitespace(right)
    if left != right:
        messages.append(
            FeedSmokeMessage(
                "failure",
                f"{label} mismatch: source={source_value!r}, generated={generated_value!r}.",
            )
        )


def _normalize_whitespace(value: str) -> str:
    """Collapse runs of whitespace to single spaces and trim the ends.

    Treats leading/trailing/internal whitespace-only differences as equal so the
    approved trailing-whitespace title differences from the cutover analysis pass
    while genuine character differences still fail.
    """
    return " ".join(value.split())


def _compare_guid_sets(
    messages: list[FeedSmokeMessage],
    *,
    source_items: tuple[RssEpisode, ...],
    generated_by_guid: dict[str, GeneratedFeedItem],
) -> None:
    source_guids = [episode.guid for episode in source_items if episode.guid]
    source_guid_set = set(source_guids)
    candidate_guid_set = set(generated_by_guid)

    missing = [guid for guid in source_guids if guid not in candidate_guid_set]
    if missing:
        messages.append(
            FeedSmokeMessage(
                "failure",
                f"Candidate feed is missing {len(missing)} source GUID(s) present in the live "
                f"feed. First missing: {missing[0]}.",
            )
        )

    extra = sorted(candidate_guid_set - source_guid_set)
    if extra:
        messages.append(
            FeedSmokeMessage(
                "failure",
                f"Candidate feed contains {len(extra)} GUID(s) not present in the live feed. "
                f"First unexpected: {extra[0]}.",
            )
        )

    latest = _latest_source_episode(source_items)
    if latest is not None and latest.guid and latest.guid not in candidate_guid_set:
        messages.append(
            FeedSmokeMessage(
                "failure",
                f"Candidate feed is missing the latest source episode {latest.guid} "
                f"({latest.title}), published {latest.published_at}. Subscribers would not "
                "receive the newest episode.",
            )
        )


def _latest_source_episode(source_items: tuple[RssEpisode, ...]) -> RssEpisode | None:
    if not source_items:
        return None
    latest: RssEpisode | None = None
    latest_at: datetime | None = None
    for episode in source_items:
        published_at = episode.published_at
        if published_at is None:
            continue
        if latest_at is None or published_at > latest_at:
            latest = episode
            latest_at = published_at
    # Fall back to the conventional newest-first first item when no item is dated.
    return latest if latest is not None else source_items[0]


def _parse_generated_item(item: ElementTree.Element) -> GeneratedFeedItem:
    enclosure = item.find("enclosure")
    return GeneratedFeedItem(
        guid=_child_text(item, "guid"),
        title=_required_child_text(item, "title"),
        published_at=_parse_rss_datetime(_child_text(item, "pubDate")),
        duration_seconds=_parse_duration(_child_text(item, "itunes:duration")),
        episode_number=_parse_int(_child_text(item, "itunes:episode")),
        podcast_episode_number=_parse_int(_child_text(item, "podcast:episode")),
        episode_type=_child_text(item, "itunes:episodeType"),
        season_number=_parse_int(_child_text(item, "itunes:season")),
        podcast_season_number=_parse_int(_child_text(item, "podcast:season")),
        keywords=_child_text(item, "itunes:keywords"),
        enclosure=_parse_enclosure(enclosure) if enclosure is not None else None,
    )


def _parse_enclosure(enclosure: ElementTree.Element) -> FeedSmokeEnclosure:
    return FeedSmokeEnclosure(
        url=enclosure.attrib.get("url", ""),
        media_type=enclosure.attrib.get("type"),
        length=_parse_int(enclosure.attrib.get("length")),
    )


def _atom_self_url(channel: ElementTree.Element) -> str | None:
    for atom_link in channel.findall("atom:link", GENERATED_FEED_NAMESPACES):
        if atom_link.attrib.get("rel") == "self":
            return atom_link.attrib.get("href")
    return None


def _child_text(element: ElementTree.Element, path: str) -> str | None:
    child = element.find(path, GENERATED_FEED_NAMESPACES)
    if child is None or child.text is None:
        return None
    return child.text.strip()


def _required_child_text(element: ElementTree.Element, path: str) -> str:
    value = _child_text(element, path)
    if value is None:
        msg = f"RSS element is missing required child {path!r}."
        raise ValueError(msg)
    return value


def _parse_rss_datetime(value: str | None) -> datetime | None:
    if value is None:
        return None
    parsed = parsedate_to_datetime(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=None)
    return parsed


def _parse_duration(value: str | None) -> int | None:
    if value is None:
        return None
    value = value.strip()
    if value.isdigit():
        return int(value)
    parts = value.split(":")
    if not 2 <= len(parts) <= 3:
        return None
    try:
        numbers = [int(part) for part in parts]
    except ValueError:
        return None
    if len(numbers) == 2:
        minutes, seconds = numbers
        return minutes * 60 + seconds
    hours, minutes, seconds = numbers
    return hours * 3600 + minutes * 60 + seconds


def _parse_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None
