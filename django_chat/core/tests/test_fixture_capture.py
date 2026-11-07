from __future__ import annotations

import io
import json
import socket
import threading
import time
from http.client import HTTPResponse
from pathlib import Path
from typing import Any

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from django_chat.core.management.commands import capture_django_chat_source_fixtures as capture

URL = "https://fixtures.example/response"


class Response(io.BytesIO):
    def __init__(self, content: bytes) -> None:
        super().__init__(content)
        self.bytes_read = 0
        self.reads = 0
        self.reader, self.writer = socket.socketpair()

    def fileno(self) -> int:
        return self.reader.fileno()

    def close(self) -> None:
        super().close()
        self.reader.close()
        self.writer.close()

    def read1(self, size: int | None = -1, /) -> bytes:
        assert size is not None and size > 0
        result = super().read1(size)
        self.bytes_read += len(result)
        self.reads += 1
        return result


def serve(monkeypatch: pytest.MonkeyPatch, response: Response) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []

    def open_response(url: str, **kwargs: Any) -> Response:
        assert url == URL
        calls.append(kwargs)
        return response

    monkeypatch.setattr(capture, "safe_urlopen", open_response)
    return calls


@pytest.mark.parametrize("timeout", [0, -1, float("nan"), float("inf"), -float("inf")])
def test_capture_rejects_invalid_timeout_before_io(
    tmp_path: Path, timeout: float, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(capture, "safe_urlopen", lambda *a, **kw: pytest.fail("unexpected fetch"))
    with pytest.raises(CommandError, match="finite and positive"):
        call_command(
            "capture_django_chat_source_fixtures", output_dir=tmp_path / "out", timeout=timeout
        )
    assert list(tmp_path.iterdir()) == []


def test_response_size_is_bounded_without_content_length(monkeypatch: pytest.MonkeyPatch) -> None:
    response = Response(b"x" * 100)
    serve(monkeypatch, response)
    monkeypatch.setattr(capture, "MAX_RESPONSE_BYTES", 16)
    with pytest.raises(CommandError, match="size limit"):
        capture.Command()._fetch_text(URL, timeout=30)
    assert response.bytes_read == 17
    assert response.closed


def test_drip_feed_obeys_transfer_deadline(monkeypatch: pytest.MonkeyPatch) -> None:
    elapsed = [0.0]

    class DripResponse(Response):
        def read1(self, size: int | None = -1, /) -> bytes:
            elapsed[0] += 0.6
            return super().read1(1)

    response = DripResponse(b"abcdefghij")
    calls = serve(monkeypatch, response)
    monkeypatch.setattr(capture.time, "monotonic", lambda: elapsed[0])
    with pytest.raises(CommandError, match="transfer deadline"):
        capture.Command()._fetch_text(URL, timeout=1)
    assert response.reads == 2
    assert response.closed
    assert calls == [{"timeout": 1, "headers": {"User-Agent": capture.USER_AGENT}}]


@pytest.mark.parametrize("content", [b"payload-secret", b"\xff", b"[]"])
def test_bad_json_is_a_safe_command_error(monkeypatch: pytest.MonkeyPatch, content: bytes) -> None:
    response = Response(content)
    serve(monkeypatch, response)
    with pytest.raises(CommandError) as error:
        capture.Command()._fetch_json(URL, timeout=30)
    assert "payload-secret" not in str(error.value)
    assert response.closed


@pytest.fixture
def synthetic_sources(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    calls: list[str] = []
    episode = {"id": "synthetic", "number": 1, "slug": "synthetic", "href": URL}

    def open_response(url: str, **kwargs: Any) -> Response:
        calls.append(url)
        if url == capture.RSS_FEED_URL:
            return Response(
                b"<rss><channel><title>Synthetic</title><item><guid>one</guid></item></channel></rss>"
            )
        if url == capture.SIMPLECAST_PODCAST_URL:
            payload = {"title": "Synthetic", "site": {"href": "https://fixtures.example/site"}}
        elif url.startswith(capture.SIMPLECAST_EPISODES_URL + "?"):
            payload = {"count": 1, "collection": [episode]}
        elif url == URL:
            payload = episode
        else:
            payload = {"collection": []}
        return Response(json.dumps(payload).encode())

    monkeypatch.setattr(capture, "safe_urlopen", open_response)
    return calls


def snapshot(directory: Path) -> dict[str, bytes]:
    return {path.name: path.read_bytes() for path in directory.iterdir()}


def seed_old(directory: Path) -> dict[str, bytes]:
    directory.mkdir()
    (directory / "rss_feed.xml").write_bytes(b"old RSS")
    (directory / "simplecast_old.json").write_bytes(b"old metadata")
    (directory / "manifest.json").write_text(
        json.dumps({"files": {"rss_feed.xml": "old", "simplecast_old.json": "old"}})
    )
    return snapshot(directory)


def test_capture_publishes_exact_manifest_and_cleans_staging(
    tmp_path: Path, synthetic_sources: list[str]
) -> None:
    output = tmp_path / "corpus"
    seed_old(output)
    call_command("capture_django_chat_source_fixtures", output_dir=output, force=True)
    files = snapshot(output)
    manifest = json.loads(files.pop("manifest.json"))
    assert set(files) == set(manifest["files"])
    assert b"Synthetic" in files["rss_feed.xml"]
    assert json.loads(files["simplecast_episode_detail_1_synthetic.json"])["id"] == "synthetic"
    assert synthetic_sources[-1] == URL
    assert len(synthetic_sources) == 7
    assert list(tmp_path.iterdir()) == [output]


def test_final_fetch_failure_preserves_complete_previous_corpus(
    tmp_path: Path, synthetic_sources: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "corpus"
    old = seed_old(output)
    opener = capture.safe_urlopen

    def fail_final(url: str, **kwargs: Any) -> Response:
        if url == URL:
            raise OSError("remote-payload-secret")
        return opener(url, **kwargs)

    monkeypatch.setattr(capture, "safe_urlopen", fail_final)
    with pytest.raises(CommandError, match="could not be fetched") as error:
        call_command("capture_django_chat_source_fixtures", output_dir=output, force=True)
    assert len(synthetic_sources) == 6  # All preceding requests completed.
    assert "remote-payload-secret" not in str(error.value)
    assert snapshot(output) == old
    assert list(tmp_path.iterdir()) == [output]


@pytest.mark.parametrize("failed_name", ["rss_feed.xml", "manifest.json"])
def test_replacement_failure_rolls_back_bytes_and_removes_new_files(
    tmp_path: Path, synthetic_sources: list[str], monkeypatch: pytest.MonkeyPatch, failed_name: str
) -> None:
    output = tmp_path / "corpus"
    old = seed_old(output)
    replace = Path.replace
    failures: list[str] = []

    def fail_replace(source: Path, target: Path) -> Path:
        if (
            source.parent.name == "corpus"
            and source.name == failed_name
            and target.parent == output
        ):
            failures.append(source.name)
            raise OSError("synthetic replacement failure")
        return replace(source, target)

    monkeypatch.setattr(Path, "replace", fail_replace)
    with pytest.raises(CommandError, match="previous generation restored"):
        call_command("capture_django_chat_source_fixtures", output_dir=output, force=True)
    assert failures == [failed_name]
    assert snapshot(output) == old
    assert list(tmp_path.iterdir()) == [output]


def test_capture_refuses_overwrite_without_force(
    tmp_path: Path, synthetic_sources: list[str]
) -> None:
    output = tmp_path / "corpus"
    old = seed_old(output)
    with pytest.raises(CommandError, match="--force"):
        call_command("capture_django_chat_source_fixtures", output_dir=output)
    assert snapshot(output) == old
    assert list(tmp_path.iterdir()) == [output]


def test_remote_filename_cannot_escape_staging() -> None:
    for identifier in ["../../escape", "bad/name", "bad\\name"]:
        with pytest.raises(CommandError, match="safe fixture identifier"):
            capture.Command()._episode_detail_filename({"number": 1, "slug": identifier})


def test_staging_write_failure_preserves_previous_generation(
    tmp_path: Path, synthetic_sources: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "corpus"
    old = seed_old(output)
    write_text = Path.write_text
    failures: list[str] = []

    def fail_write(path: Path, data: str, *args: Any, **kwargs: Any) -> int:
        if path.name == "manifest.json" and path.parent != output:
            failures.append(path.name)
            raise OSError("synthetic staging write failure")
        return write_text(path, data, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", fail_write)
    with pytest.raises(CommandError, match="no new generation"):
        call_command("capture_django_chat_source_fixtures", output_dir=output, force=True)
    assert failures == ["manifest.json"]
    assert snapshot(output) == old
    assert list(tmp_path.iterdir()) == [output]


def test_failed_rollback_retains_private_recovery_files(
    tmp_path: Path, synthetic_sources: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "corpus"
    old = seed_old(output)
    replace = Path.replace
    failures: list[str] = []

    def fail_replace(source: Path, target: Path) -> Path:
        if (source.parent.name == "corpus" and source.name == "manifest.json") or (
            source.parent.name == "restore" and source.name == "rss_feed.xml"
        ):
            failures.append(source.name)
            raise OSError("synthetic publication/recovery failure")
        return replace(source, target)

    monkeypatch.setattr(Path, "replace", fail_replace)
    with pytest.raises(CommandError, match="rollback failed") as error:
        call_command("capture_django_chat_source_fixtures", output_dir=output, force=True)
    assert failures == ["manifest.json", "rss_feed.xml"]
    recovery = next(tmp_path.glob(".django-chat-fixtures-*/backup"))
    assert str(recovery) in str(error.value)
    assert (recovery / "rss_feed.xml").read_bytes() == old["rss_feed.xml"]
    assert (recovery / "manifest.json").read_bytes() == old["manifest.json"]


def test_chunked_framing_stall_is_interrupted_by_deadline(monkeypatch: pytest.MonkeyPatch) -> None:
    # read1 may perform multiple socket reads while parsing a chunk-size line.
    # No public network: send an incomplete chunk header through a socket pair.
    reader, writer = socket.socketpair()
    with reader, writer:
        reader.settimeout(3)
        writer.sendall(b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n000")
        response = HTTPResponse(reader)
        response.begin()
        monkeypatch.setattr(capture, "safe_urlopen", lambda *a, **kw: response)
        started = time.monotonic()
        with pytest.raises(CommandError, match="transfer deadline"):
            capture.Command()._fetch_text(URL, timeout=0.1)
        assert time.monotonic() - started < 2
        assert response.isclosed()


@pytest.mark.parametrize("failure", [KeyboardInterrupt, RuntimeError])
def test_interrupted_publication_restores_previous_generation(
    tmp_path: Path,
    synthetic_sources: list[str],
    monkeypatch: pytest.MonkeyPatch,
    failure: type[BaseException],
) -> None:
    output = tmp_path / "corpus"
    old = seed_old(output)
    replace = Path.replace
    failures: list[str] = []

    def interrupt(source: Path, target: Path) -> Path:
        result = replace(source, target)
        if source.parent.name == "corpus" and source.name == "manifest.json":
            failures.append(source.name)
            raise failure("synthetic publication interruption")
        return result

    monkeypatch.setattr(Path, "replace", interrupt)
    with pytest.raises(failure):
        call_command("capture_django_chat_source_fixtures", output_dir=output, force=True)
    assert failures == ["manifest.json"]
    assert snapshot(output) == old
    assert list(tmp_path.iterdir()) == [output]


def test_watchdog_owns_socket_after_response_closes_at_eof() -> None:
    reader, writer = socket.socketpair()
    with reader, writer:
        writer.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\n{}")
        response = HTTPResponse(reader)
        response.begin()
        original_fd = response.fileno()
        reader.close()  # Mirror urllib: the makefile is now the original fd's only owner.
        with capture.Command()._response_socket(response, timeout=1) as connection:
            assert response.read1(2) == b"{}"
            assert response.isclosed()
            assert connection.fileno() not in (-1, original_fd)
            expired = threading.Event()
            capture.Command()._interrupt_socket(connection, expired)
            assert expired.is_set()
            writer.settimeout(1)
            assert writer.recv(1) == b""


def test_watchdog_expiry_is_terminal_even_before_clock_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = Response(b"{}")
    serve(monkeypatch, response)

    class EarlyTimer:
        def __init__(self, interval: float, function: Any, args: tuple[Any, ...]) -> None:
            self.function, self.args = function, args

        def start(self) -> None:
            self.function(*self.args)

        def cancel(self) -> None:
            pass

        def join(self) -> None:
            pass

    monkeypatch.setattr(capture.threading, "Timer", EarlyTimer)
    with pytest.raises(CommandError, match="transfer deadline"):
        capture.Command()._fetch_text(URL, timeout=30)
    assert response.reads == 0
    assert response.closed
