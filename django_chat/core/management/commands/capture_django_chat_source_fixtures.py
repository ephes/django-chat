"""Capture public Django Chat source fixtures for parser tests."""

from __future__ import annotations

import json
import math
import re
import shutil
import socket
import tempfile
import threading
import time
from contextlib import suppress
from datetime import UTC, datetime
from http.client import HTTPException
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from xml.etree import ElementTree

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError, CommandParser

from django_chat.imports.source_data import (
    RSS_FEED_URL,
    SIMPLECAST_DISTRIBUTION_CHANNELS_URL,
    SIMPLECAST_EPISODES_URL,
    SIMPLECAST_PODCAST_URL,
)
from django_chat.imports.url_safety import safe_urlopen

DEFAULT_FIXTURE_DIR = Path(
    "django_chat/imports/tests/fixtures/django_chat_source",
)
MAX_RESPONSE_BYTES = 16 * 1024 * 1024
READ_CHUNK_BYTES = 64 * 1024
USER_AGENT = "django-chat-fixture-capture/1.0"
RSS_FIXTURE_NAMESPACES = {
    "atom": "http://www.w3.org/2005/Atom",
    "content": "http://purl.org/rss/1.0/modules/content/",
    "googleplay": "http://www.google.com/schemas/play-podcasts/1.0",
    "itunes": "http://www.itunes.com/dtds/podcast-1.0.dtd",
    "media": "http://search.yahoo.com/mrss/",
    "podcast": "https://podcastindex.org/namespace/1.0",
}


class FixtureRecoveryRequired(CommandError):
    """Publication rollback failed; retain the private recovery directory."""


class Command(BaseCommand):
    help = (
        "Capture public Django Chat RSS and unauthenticated Simplecast endpoint "
        "fixtures. This command is read-only with respect to the database."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--output-dir",
            type=Path,
            default=DEFAULT_FIXTURE_DIR,
            help=f"Fixture directory relative to the repo root. Default: {DEFAULT_FIXTURE_DIR}",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Overwrite existing fixture files.",
        )
        parser.add_argument(
            "--timeout",
            type=float,
            default=30.0,
            help="Response transfer deadline in seconds (finite and positive). Default: 30.",
        )
        parser.add_argument(
            "--latest-limit",
            type=int,
            default=5,
            help="Number of latest episode summaries to capture. Default: 5.",
        )
        parser.add_argument(
            "--oldest-limit",
            type=int,
            default=3,
            help="Number of oldest episode summaries to capture. Default: 3.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        output_dir = self._resolve_output_dir(options["output_dir"])
        force = bool(options["force"])
        timeout = float(options["timeout"])
        latest_limit = int(options["latest_limit"])
        oldest_limit = int(options["oldest_limit"])

        if not math.isfinite(timeout) or timeout <= 0:
            raise CommandError("--timeout must be finite and positive.")

        if latest_limit < 1 or oldest_limit < 1:
            msg = "--latest-limit and --oldest-limit must be positive integers."
            raise CommandError(msg)

        output_dir.parent.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=".django-chat-fixtures-", dir=output_dir.parent))
        preserve = False
        try:
            corpus = staging / "corpus"
            corpus.mkdir()
            self._capture(
                corpus, timeout=timeout, latest_limit=latest_limit, oldest_limit=oldest_limit
            )
            self._publish(corpus, output_dir, backup=staging / "backup", force=force)
        except FixtureRecoveryRequired:
            preserve = True
            raise
        except (OSError, ValueError, ElementTree.ParseError) as exc:
            raise CommandError("Fixture capture failed; no new generation was published.") from exc
        finally:
            if not preserve:
                shutil.rmtree(staging)

        self.stdout.write(self.style.SUCCESS(f"Captured fixtures in {output_dir}"))

    def _capture(
        self, output_dir: Path, *, timeout: float, latest_limit: int, oldest_limit: int
    ) -> None:
        force = False  # All writes are to a new private staging directory.
        captured_files: dict[str, str] = {}
        rss_feed = self._rss_fixture(
            self._fetch_text(RSS_FEED_URL, timeout=timeout),
            latest_limit=latest_limit,
            oldest_limit=oldest_limit,
        )
        self._write(output_dir / "rss_feed.xml", rss_feed, force=force)
        captured_files["rss_feed.xml"] = RSS_FEED_URL

        raw_podcast_payload = self._fetch_json(SIMPLECAST_PODCAST_URL, timeout=timeout)
        podcast_payload = self._podcast_fixture(raw_podcast_payload)
        self._write_json(output_dir / "simplecast_podcast.json", podcast_payload, force=force)
        captured_files["simplecast_podcast.json"] = SIMPLECAST_PODCAST_URL

        site_url = self._object(raw_podcast_payload.get("site")).get("href")
        if isinstance(site_url, str) and site_url:
            site_payload = self._site_fixture(self._fetch_json(site_url, timeout=timeout))
            self._write_json(output_dir / "simplecast_site.json", site_payload, force=force)
            captured_files["simplecast_site.json"] = site_url

        distribution_payload = self._distribution_fixture(
            self._fetch_json(
                SIMPLECAST_DISTRIBUTION_CHANNELS_URL,
                timeout=timeout,
            )
        )
        self._write_json(
            output_dir / "simplecast_distribution_channels.json",
            distribution_payload,
            force=force,
        )
        captured_files["simplecast_distribution_channels.json"] = (
            SIMPLECAST_DISTRIBUTION_CHANNELS_URL
        )

        latest_url = f"{SIMPLECAST_EPISODES_URL}?{urlencode({'limit': latest_limit})}"
        latest_payload = self._episode_page_fixture(self._fetch_json(latest_url, timeout=timeout))
        self._write_json(
            output_dir / "simplecast_episode_list_latest.json",
            latest_payload,
            force=force,
        )
        captured_files["simplecast_episode_list_latest.json"] = latest_url

        total_count = latest_payload.get("count")
        if isinstance(total_count, int):
            oldest_offset = max(total_count - oldest_limit, 0)
            oldest_query = urlencode(
                {
                    "limit": oldest_limit,
                    "offset": oldest_offset,
                    "private": "false",
                    "sort": "latest",
                    "status": "published",
                }
            )
            oldest_url = f"{SIMPLECAST_EPISODES_URL}?{oldest_query}"
            oldest_payload = self._episode_page_fixture(
                self._fetch_json(oldest_url, timeout=timeout)
            )
            self._write_json(
                output_dir / "simplecast_episode_list_oldest.json",
                oldest_payload,
                force=force,
            )
            captured_files["simplecast_episode_list_oldest.json"] = oldest_url
        else:
            oldest_payload = {"collection": []}

        selected_details = self._selected_episode_details(latest_payload, oldest_payload)
        for episode in selected_details:
            detail_url = episode.get("href")
            if not isinstance(detail_url, str) or not detail_url:
                continue
            detail_payload = self._episode_detail_fixture(
                self._fetch_json(detail_url, timeout=timeout)
            )
            filename = self._episode_detail_filename(detail_payload)
            self._write_json(output_dir / filename, detail_payload, force=force)
            captured_files[filename] = detail_url

        manifest = {
            "captured_at": datetime.now(tz=UTC).isoformat(),
            "note": (
                "Public Django Chat source fixtures. Tests parse these local files "
                "and do not require network access."
            ),
            "files": dict(sorted(captured_files.items())),
        }
        self._write_json(output_dir / "manifest.json", manifest, force=force)

    def _resolve_output_dir(self, output_dir: Path) -> Path:
        if output_dir.is_absolute():
            return output_dir
        return Path(settings.ROOT_DIR) / output_dir

    @staticmethod
    def _response_socket(response: Any, *, timeout: float) -> socket.socket:
        # Keep our own socket reference: HTTPResponse can close its fd during
        # read1 at EOF, before our finally block runs. These are public APIs.
        wrapper = socket.socket(fileno=response.fileno())
        try:
            connection = wrapper.dup()
        finally:
            wrapper.detach()  # The response owns the original descriptor.
        connection.settimeout(timeout)
        return connection

    @staticmethod
    def _interrupt_socket(connection: socket.socket, expired: threading.Event) -> None:
        expired.set()
        # The response may already have reached EOF.
        with suppress(OSError):
            connection.shutdown(socket.SHUT_RDWR)

    def _fetch_text(self, url: str, *, timeout: float) -> str:
        if not math.isfinite(timeout) or timeout <= 0:
            raise CommandError("--timeout must be finite and positive.")
        deadline = time.monotonic() + timeout
        expired = threading.Event()
        content = bytearray()
        try:
            with (
                safe_urlopen(url, timeout=timeout, headers={"User-Agent": USER_AGENT}) as response,
                self._response_socket(response, timeout=timeout) as connection,
            ):
                watchdog = threading.Timer(
                    max(0, deadline - time.monotonic()),
                    self._interrupt_socket,
                    args=(connection, expired),
                )
                watchdog.daemon = True
                watchdog.start()
                try:
                    while True:
                        if expired.is_set() or time.monotonic() >= deadline:
                            raise CommandError("Fixture response exceeded its transfer deadline.")
                        chunk = response.read1(
                            min(READ_CHUNK_BYTES, MAX_RESPONSE_BYTES + 1 - len(content))
                        )
                        if expired.is_set() or time.monotonic() >= deadline:
                            raise CommandError("Fixture response exceeded its transfer deadline.")
                        content.extend(chunk)
                        if len(content) > MAX_RESPONSE_BYTES:
                            raise CommandError("Fixture response exceeded the 16 MiB size limit.")
                        if not chunk:
                            return content.decode("utf-8")
                finally:
                    watchdog.cancel()
                    watchdog.join()
        except (OSError, ValueError, HTTPException) as exc:
            if expired.is_set() or time.monotonic() >= deadline:
                raise CommandError("Fixture response exceeded its transfer deadline.") from exc
            raise CommandError("Fixture response could not be fetched or decoded.") from exc

    def _fetch_json(self, url: str, *, timeout: float) -> dict[str, Any]:
        text = self._fetch_text(url, timeout=timeout)
        try:
            payload = json.loads(text)
        except ValueError as exc:
            raise CommandError("Fixture response is not valid JSON.") from exc
        if not isinstance(payload, dict):
            msg = "Expected a JSON object in the fixture response."
            raise CommandError(msg)
        return payload

    def _write(self, path: Path, content: str, *, force: bool) -> None:
        if path.exists() and not force:
            msg = f"{path} already exists; pass --force to overwrite fixtures."
            raise CommandError(msg)
        path.write_text(content, encoding="utf-8")

    def _write_json(self, path: Path, payload: dict[str, Any], *, force: bool) -> None:
        self._write(
            path,
            json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            force=force,
        )

    def _publish(self, corpus: Path, output_dir: Path, *, backup: Path, force: bool) -> None:
        names = {path.name for path in corpus.iterdir()}
        previous: set[str] = set()
        manifest = output_dir / "manifest.json"
        if manifest.exists():
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            files = payload.get("files") if isinstance(payload, dict) else None
            if not isinstance(files, dict) or any(not self._fixture_name(name) for name in files):
                raise CommandError("Existing fixture manifest is invalid; publication refused.")
            previous = set(files)
        # Manifest is the commit marker; publish it after additions and removals.
        ordered = sorted((names | previous) - {"manifest.json"}) + ["manifest.json"]
        if not force and any((output_dir / name).exists() for name in ordered):
            raise CommandError("Fixtures already exist; pass --force to overwrite fixtures.")
        output_dir.mkdir(parents=True, exist_ok=True)
        backup.mkdir()
        existed = {name for name in ordered if (output_dir / name).exists()}
        for name in existed:
            shutil.copy2(output_dir / name, backup / name)
        (backup / "recovery.json").write_text(
            json.dumps({"restore": sorted(existed), "remove": sorted(set(ordered) - existed)}),
            encoding="utf-8",
        )
        restore_dir = backup.parent / "restore"
        restore_dir.mkdir()
        changed: list[str] = []
        try:
            for name in ordered:
                changed.append(name)
                target = output_dir / name
                if name in names:
                    (corpus / name).replace(target)
                else:
                    target.unlink(missing_ok=True)
        except BaseException as exc:
            failed_restores: list[str] = []
            for name in reversed(changed):
                try:
                    target = output_dir / name
                    if name in existed:
                        shutil.copy2(backup / name, restore_dir / name)
                        (restore_dir / name).replace(target)
                    else:
                        target.unlink(missing_ok=True)
                except BaseException:
                    failed_restores.append(name)
            if failed_restores:
                raise FixtureRecoveryRequired(
                    f"Fixture rollback failed for {', '.join(failed_restores)}; "
                    f"recover using {backup / 'recovery.json'} and its complete backup."
                ) from exc
            if isinstance(exc, OSError):
                raise CommandError(
                    "Fixture publication failed; previous generation restored."
                ) from exc
            raise

    @staticmethod
    def _fixture_name(name: str) -> bool:
        return name == "rss_feed.xml" or bool(
            re.fullmatch(r"simplecast_[A-Za-z0-9_-]+\.json", name)
        )

    def _rss_fixture(self, xml_text: str, *, latest_limit: int, oldest_limit: int) -> str:
        for prefix, uri in RSS_FIXTURE_NAMESPACES.items():
            ElementTree.register_namespace(prefix, uri)

        root = ElementTree.fromstring(xml_text)
        channel = root.find("channel")
        if channel is None:
            msg = "RSS feed response does not contain a channel element."
            raise CommandError(msg)

        items = channel.findall("item")
        latest_items = items[:latest_limit]
        oldest_items = items[-oldest_limit:] if oldest_limit else []
        selected_by_guid: dict[str, ElementTree.Element] = {}
        for item in latest_items + oldest_items:
            guid = item.findtext("guid")
            selected_by_guid[guid or str(id(item))] = item

        for item in items:
            channel.remove(item)
        channel.extend(selected_by_guid.values())

        return (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            + ElementTree.tostring(
                root,
                encoding="unicode",
            )
            + "\n"
        )

    def _selected_episode_details(
        self,
        latest_payload: dict[str, Any],
        oldest_payload: dict[str, Any],
    ) -> tuple[dict[str, Any], ...]:
        candidates = [
            *self._collection(latest_payload)[:1],
            *self._collection(oldest_payload),
        ]
        selected: dict[str, dict[str, Any]] = {}
        for episode in candidates:
            episode_id = episode.get("id")
            if isinstance(episode_id, str):
                selected[episode_id] = episode
        return tuple(selected.values())

    def _collection(self, payload: dict[str, Any]) -> tuple[dict[str, Any], ...]:
        collection = payload.get("collection")
        if not isinstance(collection, list):
            return ()
        return tuple(item for item in collection if isinstance(item, dict))

    def _object(self, value: Any) -> dict[str, Any]:
        return value if isinstance(value, dict) else {}

    def _episode_detail_filename(self, payload: dict[str, Any]) -> str:
        number = payload.get("number")
        slug = payload.get("slug")
        episode_id = payload.get("id")
        filename = ""
        if isinstance(number, int) and isinstance(slug, str) and slug:
            filename = f"simplecast_episode_detail_{number}_{slug}.json"
        elif isinstance(episode_id, str) and episode_id:
            filename = f"simplecast_episode_detail_{episode_id}.json"
        if self._fixture_name(filename):
            return filename
        raise CommandError("Episode detail response does not include a safe fixture identifier.")

    def _podcast_fixture(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "authors": {
                "collection": [
                    self._pick(author, ("href", "id", "name", "hide"))
                    for author in self._collection(self._object(payload.get("authors")))
                ],
                "href": self._object(payload.get("authors")).get("href"),
            },
            "copyright": payload.get("copyright"),
            "created_at": payload.get("created_at"),
            "description": payload.get("description"),
            "distribution_channels": self._pick(
                self._object(payload.get("distribution_channels")),
                ("href",),
            ),
            "enable_feed": payload.get("enable_feed"),
            "episodes": self._pick(self._object(payload.get("episodes")), ("href", "count")),
            "feed_url": payload.get("feed_url"),
            "href": payload.get("href"),
            "id": payload.get("id"),
            "image_url": payload.get("image_url"),
            "is_explicit": payload.get("is_explicit"),
            "language": payload.get("language"),
            "published_at": payload.get("published_at"),
            "site": self._pick(
                self._object(payload.get("site")),
                ("href", "url", "subdomain", "site_enabled", "id", "external_website", "cname_url"),
            ),
            "status": payload.get("status"),
            "subtitle": payload.get("subtitle"),
            "time_zone": payload.get("time_zone"),
            "title": payload.get("title"),
            "type": payload.get("type"),
            "updated_at": payload.get("updated_at"),
        }

    def _site_fixture(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "cname_url": payload.get("cname_url"),
            "color": payload.get("color"),
            "created_at": payload.get("created_at"),
            "external_website": payload.get("external_website"),
            "favicon_url": payload.get("favicon_url"),
            "href": payload.get("href"),
            "id": payload.get("id"),
            "legacy_hosts": payload.get("legacy_hosts"),
            "menu_links": self._link_collection_fixture(payload.get("menu_links")),
            "podcast": self._pick(
                self._object(payload.get("podcast")),
                ("href", "title", "status", "image_url", "id", "episodes", "created_at"),
            ),
            "privacy_policy_link": payload.get("privacy_policy_link"),
            "privacy_policy_text": payload.get("privacy_policy_text"),
            "site_enabled": payload.get("site_enabled"),
            "site_links": self._link_collection_fixture(payload.get("site_links")),
            "subdomain": payload.get("subdomain"),
            "theme": payload.get("theme"),
            "updated_at": payload.get("updated_at"),
            "url": payload.get("url"),
        }

    def _link_collection_fixture(self, payload: Any) -> dict[str, Any]:
        payload_object = self._object(payload)
        return {
            "collection": [
                self._pick(
                    item,
                    ("href", "url", "order", "new_window", "name", "location", "is_visible", "id"),
                )
                for item in self._collection(payload_object)
            ],
            "href": payload_object.get("href"),
        }

    def _distribution_fixture(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "collection": [
                {
                    "distribution_channel": self._pick(
                        self._object(item.get("distribution_channel")),
                        ("href", "name", "id"),
                    ),
                    "href": item.get("href"),
                    "id": item.get("id"),
                    "url": item.get("url"),
                }
                for item in self._collection(payload)
            ],
            "href": payload.get("href"),
        }

    def _episode_page_fixture(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "average_duration": payload.get("average_duration"),
            "collection": [
                self._episode_summary_fixture(item) for item in self._collection(payload)
            ],
            "count": payload.get("count"),
            "href": payload.get("href"),
            "pages": payload.get("pages"),
        }

    def _episode_detail_fixture(self, payload: dict[str, Any]) -> dict[str, Any]:
        detail = self._episode_summary_fixture(payload)
        detail.update(
            {
                "audio_file_size": payload.get("audio_file_size"),
                "audio_file_url": payload.get("audio_file_url"),
                "episode_url": payload.get("episode_url"),
                "is_explicit": payload.get("is_explicit"),
                "long_description": payload.get("long_description"),
                "transcription": payload.get("transcription"),
            }
        )
        return detail

    def _episode_summary_fixture(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "audio_status": payload.get("audio_status"),
            "description": payload.get("description"),
            "duration": payload.get("duration"),
            "enclosure_url": payload.get("enclosure_url"),
            "guid": payload.get("guid"),
            "href": payload.get("href"),
            "id": payload.get("id"),
            "image_url": payload.get("image_url"),
            "is_hidden": payload.get("is_hidden"),
            "number": payload.get("number"),
            "published_at": payload.get("published_at"),
            "season": self._pick(self._object(payload.get("season")), ("href", "number")),
            "slug": payload.get("slug"),
            "status": payload.get("status"),
            "title": payload.get("title"),
            "type": payload.get("type"),
            "updated_at": payload.get("updated_at"),
        }

    def _pick(self, payload: dict[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
        return {key: payload.get(key) for key in keys}
