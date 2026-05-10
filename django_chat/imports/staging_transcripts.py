from __future__ import annotations

import json
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Any, cast
from urllib.parse import quote, urljoin
from urllib.request import Request, urlopen

from cast.models import Episode
from django.apps import apps
from django.conf import settings
from django.core.files.base import ContentFile

USER_AGENT = "django-chat-staging-transcript-import/1.0"
DEFAULT_STAGING_HOST = "https://djangochat.staging.django-cast.com"

TextFetcher = Callable[[str, float], str]
JsonObject = dict[str, Any]


@dataclass(frozen=True)
class StagingTranscriptImportItem:
    slug: str
    imported: bool
    segment_count: int
    reason: str = ""


@dataclass(frozen=True)
class StagingTranscriptImportResult:
    items: tuple[StagingTranscriptImportItem, ...]

    @property
    def imported_count(self) -> int:
        return sum(1 for item in self.items if item.imported)

    @property
    def skipped_count(self) -> int:
        return sum(1 for item in self.items if not item.imported)


def import_staging_transcripts(
    *,
    host: str = DEFAULT_STAGING_HOST,
    podcast_slug: str | None = None,
    slugs: Iterable[str] | None = None,
    timeout: float = 30.0,
    text_fetcher: TextFetcher | None = None,
) -> StagingTranscriptImportResult:
    """Import django-cast transcript artifacts from the staging Podlove API."""

    fetch_text = text_fetcher or default_fetch_text
    podcast_slug = podcast_slug or settings.DJANGO_CHAT_PODCAST_SLUG
    requested_slugs = tuple(slugs or ())
    episodes = Episode.objects.select_related("podcast_audio").filter(podcast_audio__isnull=False)
    if requested_slugs:
        episodes = episodes.filter(slug__in=requested_slugs)
    episodes = episodes.order_by("slug")

    items = [
        import_staging_transcript_for_episode(
            episode,
            host=host,
            podcast_slug=podcast_slug,
            timeout=timeout,
            text_fetcher=fetch_text,
        )
        for episode in episodes
    ]

    imported_slugs = {item.slug for item in items}
    for slug in requested_slugs:
        if slug not in imported_slugs:
            reason = (
                "local episode has no copied audio"
                if Episode.objects.filter(slug=slug).exists()
                else "local episode not found"
            )
            items.append(
                StagingTranscriptImportItem(
                    slug=slug,
                    imported=False,
                    segment_count=0,
                    reason=reason,
                )
            )

    return StagingTranscriptImportResult(items=tuple(items))


def import_staging_transcript_for_episode(
    episode: Episode,
    *,
    host: str = DEFAULT_STAGING_HOST,
    podcast_slug: str | None = None,
    timeout: float = 30.0,
    text_fetcher: TextFetcher | None = None,
) -> StagingTranscriptImportItem:
    fetch_text = text_fetcher or default_fetch_text
    podcast_slug = podcast_slug or settings.DJANGO_CHAT_PODCAST_SLUG
    episode_slug = str(episode.slug)
    if episode.podcast_audio is None:
        return StagingTranscriptImportItem(
            slug=episode_slug,
            imported=False,
            segment_count=0,
            reason="local episode has no copied audio",
        )

    episode_url = _staging_episode_url(host, podcast_slug, episode_slug)
    try:
        detail_html = fetch_text(episode_url, timeout)
        podlove_api_url = extract_podlove_api_url(detail_html, base_url=episode_url)
        podlove_payload = json.loads(fetch_text(podlove_api_url, timeout))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return StagingTranscriptImportItem(
            slug=episode_slug,
            imported=False,
            segment_count=0,
            reason=str(exc),
        )

    segments = _normalized_segments(podlove_payload.get("transcripts"))
    if not segments:
        return StagingTranscriptImportItem(
            slug=episode_slug,
            imported=False,
            segment_count=0,
            reason="staging Podlove API returned no transcript segments",
        )

    transcript_model = cast(Any, apps.get_model("cast", "Transcript"))
    transcript, _created = transcript_model.objects.get_or_create(audio=episode.podcast_audio)
    podlove = {"transcripts": segments}
    _replace_text_file(
        transcript.podlove,
        f"django-chat-staging/{episode_slug}.podlove.json",
        podlove,
    )
    _replace_file(
        transcript.vtt,
        f"django-chat-staging/{episode_slug}.vtt",
        ContentFile(podlove_segments_to_vtt(segments)),
    )
    _replace_text_file(
        transcript.dote,
        f"django-chat-staging/{episode_slug}.dote.json",
        podlove_segments_to_dote(segments),
    )
    transcript.save(update_fields=["podlove", "vtt", "dote"])

    return StagingTranscriptImportItem(
        slug=episode_slug,
        imported=True,
        segment_count=len(segments),
    )


def extract_podlove_api_url(html: str, *, base_url: str) -> str:
    parser = _PodlovePlayerParser()
    parser.feed(html)
    if not parser.data_url:
        msg = "staging episode page did not contain a podlove-player data-url"
        raise ValueError(msg)
    return urljoin(base_url, parser.data_url)


def podlove_segments_to_vtt(segments: list[JsonObject]) -> str:
    lines = ["WEBVTT", ""]
    for segment in segments:
        text = str(segment.get("text", "")).strip()
        start = str(segment.get("start", "")).strip()
        end = str(segment.get("end", "")).strip()
        if not (text and start and end):
            continue
        lines.append(f"{start} --> {end}")
        lines.append(text)
        lines.append("")
    return "\n".join(lines) + "\n"


def podlove_segments_to_dote(segments: list[JsonObject]) -> JsonObject:
    return {
        "lines": [
            {
                "startTime": _dote_time(str(segment["start"])),
                "endTime": _dote_time(str(segment["end"])),
                "speakerDesignation": str(segment.get("speaker") or ""),
                "text": str(segment["text"]),
            }
            for segment in segments
            if segment.get("start") and segment.get("end") and segment.get("text")
        ]
    }


def default_fetch_text(url: str, timeout: float) -> str:
    request = Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/json;q=0.9,*/*;q=0.8"},
    )
    with urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8")


def _normalized_segments(value: Any) -> list[JsonObject]:
    if not isinstance(value, list):
        return []
    segments = []
    for segment in value:
        if not isinstance(segment, dict):
            continue
        text = str(segment.get("text", "")).strip()
        start = str(segment.get("start", "")).strip()
        end = str(segment.get("end", "")).strip()
        if not (text and start and end):
            continue
        segments.append(
            {
                "start": start,
                "start_ms": segment.get("start_ms"),
                "end": end,
                "end_ms": segment.get("end_ms"),
                "speaker": str(segment.get("speaker") or ""),
                "voice": str(segment.get("voice") or ""),
                "text": text,
            }
        )
    return segments


def _replace_text_file(field: Any, name: str, data: JsonObject) -> None:
    _replace_file(field, name, ContentFile(json.dumps(data, ensure_ascii=False, indent=2) + "\n"))


def _replace_file(field: Any, name: str, content: ContentFile) -> None:
    if field and field.name:
        field.delete(save=False)
    field.save(name, content, save=False)


def _dote_time(value: str) -> str:
    """Convert Podlove HH:MM:SS.mmm timestamps; values without a dot pass through."""
    return value.replace(".", ",", 1)


def _staging_episode_url(host: str, podcast_slug: str, episode_slug: str) -> str:
    base = host.rstrip("/") + "/"
    return urljoin(base, f"{quote(podcast_slug.strip('/'))}/{quote(episode_slug)}/")


class _PodlovePlayerParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.data_url = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "podlove-player" or self.data_url:
            return
        data = dict(attrs)
        self.data_url = data.get("data-url") or ""
