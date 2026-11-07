"""Bounded HTTP body reads, using public response/socket APIs."""

from __future__ import annotations

import math
import socket
import threading
import time
from collections.abc import Iterator
from contextlib import suppress
from typing import Any

TEXT_MAX_BYTES = 16 * 1024 * 1024
IMAGE_MAX_BYTES = 20 * 1024 * 1024
AUDIO_MAX_BYTES = 1024 * 1024 * 1024
AUDIO_TRANSFER_SECONDS = 30 * 60
READ_CHUNK_BYTES = 64 * 1024


def transfer_deadline(seconds: float) -> float:
    if not math.isfinite(seconds) or seconds <= 0:
        raise ValueError("Transfer timeout must be finite and positive.")
    return time.monotonic() + seconds


def _response_socket(response: Any, timeout: float) -> socket.socket:
    wrapper = socket.socket(fileno=response.fileno())
    try:
        connection = wrapper.dup()
    finally:
        wrapper.detach()  # The response owns the original descriptor.
    connection.settimeout(timeout)
    return connection


def _interrupt(connection: socket.socket, expired: threading.Event) -> None:
    expired.set()
    with suppress(OSError):
        connection.shutdown(socket.SHUT_RDWR)


def bounded_chunks(
    response: Any,
    *,
    max_bytes: int,
    deadline: float,
    timeout: float,
    chunk_size: int = READ_CHUNK_BYTES,
) -> Iterator[bytes]:
    """Reject over-budget or incomplete bodies; interrupt stalled chunk framing.

    The caller owns/always closes the response. The deadline starts before opening
    it. Like the fixture capture reader, a duplicate socket lets the watchdog
    interrupt even an HTTP chunk header that never finishes arriving.
    """
    if chunk_size <= 0:
        raise ValueError("Read chunk size must be positive.")
    raw_length = response.headers.get("Content-Length")
    declared = None
    if raw_length is not None:
        if not raw_length.isascii() or not raw_length.isdigit() or len(raw_length) > 20:
            raise ValueError("Invalid response Content-Length.")
        declared = int(raw_length)
        if declared > max_bytes:
            raise ValueError("Response exceeded its byte budget.")
    if response.headers.get("Content-Encoding", "identity").lower() != "identity":
        raise ValueError("Encoded response bodies are not supported.")
    expired = threading.Event()
    with _response_socket(response, timeout) as connection:
        watchdog = threading.Timer(
            max(0, deadline - time.monotonic()), _interrupt, args=(connection, expired)
        )
        watchdog.daemon = True
        watchdog.start()
        received = 0
        try:
            while True:
                if expired.is_set() or time.monotonic() >= deadline:
                    raise ValueError("Response exceeded its transfer deadline.")
                chunk = response.read1(min(chunk_size, max_bytes + 1 - received))
                if expired.is_set() or time.monotonic() >= deadline:
                    raise ValueError("Response exceeded its transfer deadline.")
                received += len(chunk)
                if received > max_bytes:
                    raise ValueError("Response exceeded its byte budget.")
                if not chunk:
                    if declared is not None and received != declared:
                        raise ValueError("Response length does not match Content-Length.")
                    return
                yield chunk
        except OSError as exc:
            if expired.is_set() or time.monotonic() >= deadline:
                raise ValueError("Response exceeded its transfer deadline.") from exc
            raise
        finally:
            watchdog.cancel()
            watchdog.join()
