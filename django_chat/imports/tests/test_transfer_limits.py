from __future__ import annotations

import io
import socket
import time
from http.client import HTTPResponse
from pathlib import Path

import pytest

from django_chat.imports import import_catalog as catalog
from django_chat.imports import import_sample as sample
from django_chat.imports import staging_transcripts as staging
from django_chat.imports import transfer_limits as limits

URL = "https://media.example.test/synthetic"


class Response(io.BytesIO):
    def __init__(self, body: bytes, headers: dict[str, str]) -> None:
        super().__init__(body)
        self.headers = headers
        self.sizes: list[int] = []

    def read1(self, size: int | None = -1, /) -> bytes:
        assert size is not None and 0 < size <= limits.READ_CHUNK_BYTES
        self.sizes.append(size)
        return super().read1(size)


@pytest.fixture
def fake_socket(monkeypatch):
    reader, writer = socket.socketpair()
    with reader, writer:
        monkeypatch.setattr(limits, "_response_socket", lambda response, timeout: reader.dup())
        yield


def fetch(kind: str, tmp_path: Path):
    if kind == "catalog-text":
        return catalog.default_fetch_text(URL, 1)
    if kind == "staging-text":
        return staging.default_fetch_text(URL, 1)
    if kind == "catalog-image":
        return catalog.live_cover_image_downloader(1)(URL)
    if kind == "sample-image":
        return sample.default_download_image(URL)
    if kind == "sample-audio":
        return sample.default_download_audio(URL).content
    result = sample.default_stream_download_audio(URL, tmp_path / "audio")
    assert result.byte_size == 3
    return result.path.read_bytes()


KINDS = [
    "catalog-text",
    "staging-text",
    "catalog-image",
    "sample-image",
    "sample-audio",
    "stream-audio",
]


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("mode", ["normal", "oversized", "omitted-length", "truncated", "drip"])
def test_default_fetchers_bound_and_close(kind, mode, tmp_path, monkeypatch, fake_socket):
    body = b"abc" if mode in {"normal", "truncated", "drip"} else b"x" * 9
    headers = {} if mode == "omitted-length" else {"Content-Length": str(len(body))}
    if mode == "truncated":
        headers["Content-Length"] = "7"
    response = Response(body, headers)
    module = (
        catalog if kind.startswith("catalog") else staging if kind.startswith("staging") else sample
    )
    monkeypatch.setattr(module, "safe_urlopen", lambda *a, **kw: response)
    for name in ("TEXT_MAX_BYTES", "IMAGE_MAX_BYTES", "AUDIO_MAX_BYTES"):
        monkeypatch.setattr(module, name, 8, raising=False)
    if mode == "drip":
        clock = [100.0]
        monkeypatch.setattr(limits.time, "monotonic", lambda: clock[0])
        original = response.read1

        def drip(size=-1):
            clock[0] += 4000  # Exceed even the audio deadline on the first byte.
            return original(1)

        monkeypatch.setattr(response, "read1", drip)
    if mode == "normal":
        assert fetch(kind, tmp_path) in (b"abc", "abc")
        assert response.sizes
    else:
        with pytest.raises(ValueError, match="budget|length|deadline"):
            fetch(kind, tmp_path)
        assert not (tmp_path / "audio").exists()
    assert response.closed


def test_stalled_chunk_framing_is_interrupted(monkeypatch):
    reader, writer = socket.socketpair()
    with reader, writer:
        reader.settimeout(3)
        writer.sendall(b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n000")
        response = HTTPResponse(reader)
        response.begin()
        monkeypatch.setattr(catalog, "safe_urlopen", lambda *a, **kw: response)
        started = time.monotonic()
        with pytest.raises(ValueError, match="transfer deadline"):
            catalog.default_fetch_text(URL, 0.05)
        assert time.monotonic() - started < 2
        assert response.isclosed()


def test_stream_download_does_not_remove_preexisting_destination(tmp_path):
    destination = tmp_path / "audio"
    destination.write_bytes(b"previous generation")
    with pytest.raises(FileExistsError):
        sample.default_stream_download_audio(URL, destination)
    assert destination.read_bytes() == b"previous generation"


@pytest.mark.django_db
def test_incomplete_audio_never_reaches_publication(tmp_path, monkeypatch):
    result = sample.import_django_chat_sample()
    metadata = result.episode_metadata[0]
    published = []
    monkeypatch.setattr(
        sample, "_save_downloaded_episode_audio", lambda *a, **kw: published.append(kw)
    )
    with pytest.raises(ValueError, match="expected byte size"):
        sample.copy_django_chat_sample_audio(
            (metadata,),
            audio_downloader=lambda url: sample.DownloadedAudio(b"abc", content_length=7),
        )

    def download(url, destination):
        destination.write_bytes(b"abc")
        return sample.DownloadedAudioFile(destination, 3, content_length=7)

    with pytest.raises(ValueError, match="expected byte size"):
        sample.copy_django_chat_catalog_audio((metadata,), audio_downloader=download)
    assert published == []


def test_watchdog_socket_preserves_configured_operation_timeout():
    reader, writer = socket.socketpair()
    with reader, writer:
        reader.settimeout(0.1)
        writer.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 3\r\n\r\n")
        response = HTTPResponse(reader)
        response.begin()
        with response, limits._response_socket(response, 0.1) as connection:
            assert connection.gettimeout() == 0.1
            with pytest.raises(TimeoutError):
                connection.recv(1)
