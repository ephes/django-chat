from __future__ import annotations

import json
from collections.abc import Callable, Iterable
from contextlib import suppress
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Any, cast
from urllib.parse import parse_qs, quote, urljoin, urlparse
from uuid import uuid4

from cast.models import Episode
from django.apps import apps
from django.conf import settings
from django.core.files.base import ContentFile

from django_chat.imports.url_safety import safe_urlopen

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


@dataclass(frozen=True)
class ReplacedFile:
    old_storage: Any
    old_name: str
    new_storage: Any
    new_name: str


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
    replacements = []
    try:
        replacements.append(
            _replace_text_file(
                transcript.podlove,
                f"django-chat-staging/{episode_slug}.podlove.json",
                podlove,
            )
        )
        replacements.append(
            _replace_file(
                transcript.vtt,
                f"django-chat-staging/{episode_slug}.vtt",
                ContentFile(podlove_segments_to_vtt(segments)),
            )
        )
        replacements.append(
            _replace_text_file(
                transcript.dote,
                f"django-chat-staging/{episode_slug}.dote.json",
                podlove_segments_to_dote(segments),
            )
        )
        transcript.save(update_fields=["podlove", "vtt", "dote"])
    except Exception:
        _delete_replacement_files(replacements, use_new=True)
        raise
    _delete_replacement_files(replacements, use_new=False)

    return StagingTranscriptImportItem(
        slug=episode_slug,
        imported=True,
        segment_count=len(segments),
    )


def extract_podlove_api_url(html: str, *, base_url: str) -> str:
    """Locate the staging Podlove transcript API URL for an episode page.

    Staging renders django-cast's custom player, whose JSON payload script
    carries the audio id and a transcript URL with a ``post_id`` query
    parameter. The Podlove API URL is rebuilt from those two numeric ids on
    the page's own origin — never from a URL string in the (untrusted) page
    body — so a tampered/compromised page cannot point the follow-up fetch at
    `file:///…` or an internal/metadata host (SSRF / local file read).
    """
    parser = _CastPlayerPayloadParser()
    parser.feed(html)
    payload_text = parser.payload_text()
    if not payload_text:
        msg = "staging episode page did not contain a cast-audio-player payload"
        raise ValueError(msg)
    try:
        payload = json.loads(payload_text)
    except json.JSONDecodeError as exc:
        msg = f"staging cast-audio-player payload is not valid JSON: {exc}"
        raise ValueError(msg) from None
    audio_id = payload.get("audioId") if isinstance(payload, dict) else None
    if not isinstance(audio_id, int) or isinstance(audio_id, bool):
        msg = "staging cast-audio-player payload has no numeric audioId"
        raise ValueError(msg)
    transcript = payload.get("transcript")
    transcript_url = str(transcript.get("url") or "") if isinstance(transcript, dict) else ""
    if not transcript_url:
        msg = "staging episode page exposes no transcript for this episode"
        raise ValueError(msg)
    post_id_values = parse_qs(urlparse(transcript_url).query).get("post_id", [])
    post_id = post_id_values[0] if post_id_values else ""
    if not post_id.isdigit():
        msg = "staging cast-audio-player transcript URL has no numeric post_id"
        raise ValueError(msg)
    base = urlparse(base_url)
    if base.scheme not in {"http", "https"} or not base.netloc:
        msg = f"unexpected staging episode page URL: {base_url!r}"
        raise ValueError(msg)
    return f"{base.scheme}://{base.netloc}/api/audios/podlove/{audio_id}/post/{post_id}/"


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
    with safe_urlopen(
        url,
        timeout=timeout,
        headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/json;q=0.9,*/*;q=0.8"},
    ) as response:
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


def _replace_text_file(field: Any, name: str, data: JsonObject) -> ReplacedFile | None:
    return _replace_file(
        field, name, ContentFile(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    )


def _replace_file(field: Any, name: str, content: ContentFile) -> ReplacedFile | None:
    old_name = field.name if field and field.name else ""
    old_storage = field.storage if old_name else None
    replacement_name = _replacement_name(name)
    field.save(replacement_name, content, save=False)
    if old_name and old_name != field.name:
        return ReplacedFile(
            old_storage=old_storage,
            old_name=old_name,
            new_storage=field.storage,
            new_name=field.name,
        )
    return None


def _replacement_name(name: str) -> str:
    unique_suffix = uuid4().hex[:12]
    for suffix in (".podlove.json", ".dote.json"):
        if name.endswith(suffix):
            return f"{name[: -len(suffix)]}-{unique_suffix}{suffix}"
    stem, dot, suffix = name.rpartition(".")
    if dot:
        return f"{stem}-{unique_suffix}.{suffix}"
    return f"{name}-{unique_suffix}"


def _delete_replacement_files(
    replacements: Iterable[ReplacedFile | None], *, use_new: bool
) -> None:
    for replacement in replacements:
        if replacement is None:
            continue
        storage = replacement.new_storage if use_new else replacement.old_storage
        name = replacement.new_name if use_new else replacement.old_name
        with suppress(Exception):
            storage.delete(name)


def _dote_time(value: str) -> str:
    """Convert Podlove HH:MM:SS.mmm timestamps; values without a dot pass through."""
    return value.replace(".", ",", 1)


def _staging_episode_url(host: str, podcast_slug: str, episode_slug: str) -> str:
    base = host.rstrip("/") + "/"
    return urljoin(base, f"{quote(podcast_slug.strip('/'))}/{quote(episode_slug)}/")


class _CastPlayerPayloadParser(HTMLParser):
    """Collect the JSON payload script of the first <cast-audio-player>.

    The payload `<script id="…" type="application/json">` precedes the player
    element in django-cast's markup, so every id'd script's text is collected
    and the player's ``data-payload`` id is resolved after the full parse.
    """

    def __init__(self) -> None:
        super().__init__()
        self._payload_id = ""
        self._scripts: dict[str, list[str]] = {}
        self._open_script_id = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        data = dict(attrs)
        if tag == "cast-audio-player" and not self._payload_id:
            self._payload_id = data.get("data-payload") or ""
        elif tag == "script":
            script_id = data.get("id") or ""
            self._open_script_id = script_id
            if script_id:
                self._scripts.setdefault(script_id, [])

    def handle_endtag(self, tag: str) -> None:
        if tag == "script":
            self._open_script_id = ""

    def handle_data(self, data: str) -> None:
        if self._open_script_id:
            self._scripts[self._open_script_id].append(data)

    def payload_text(self) -> str:
        return "".join(self._scripts.get(self._payload_id, [])).strip()
