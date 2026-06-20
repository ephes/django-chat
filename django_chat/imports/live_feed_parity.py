"""Live feed parity checker for the Simplecast -> self-hosted feed cutover.

Fetches the live Simplecast RSS feed and an operator-supplied candidate feed
URL (the exact django-cast / S3 / CDN XML a podcast client would fetch) and runs
the strict Phase 2 parity gates from ``docs/feed-cutover-analysis.md`` over them.

Every outbound fetch goes through :func:`safe_urlopen` so the SSRF guard (scheme
check + connect-time IP pinning + redirect re-validation) covers both the source
and candidate URLs. Fetch and parse failures are surfaced as a single ``failure``
:class:`FeedSmokeMessage` rather than raised, so the command still prints a
report and exits non-zero.
"""

from __future__ import annotations

import http.client
from urllib.error import HTTPError
from xml.etree import ElementTree

from django_chat.imports.feed_smoke import (
    FeedSmokeMessage,
    FeedSmokeResult,
    compare_source_to_generated_feed,
    parse_generated_podcast_feed,
)
from django_chat.imports.source_data import RSS_FEED_URL, parse_rss_feed
from django_chat.imports.url_safety import UnsafeURLError, safe_urlopen

DEFAULT_FETCH_TIMEOUT = 30.0
FEED_FETCH_USER_AGENT = "django-chat-feed-parity/1.0 (+https://djangochat.com)"
FEED_FETCH_HEADERS = {
    "User-Agent": FEED_FETCH_USER_AGENT,
    "Accept": "application/rss+xml, application/xml;q=0.9, */*;q=0.8",
}


class FeedFetchError(Exception):
    """A feed URL could not be fetched as a usable HTTP 200 body."""


def fetch_feed_bytes(url: str, *, timeout: float = DEFAULT_FETCH_TIMEOUT) -> bytes:
    """Fetch ``url`` through :func:`safe_urlopen`, returning the response body.

    Raises :class:`FeedFetchError` for an SSRF-refused URL, a non-2xx status, or
    any connection/transport error so callers can surface one failure message.
    """

    try:
        with safe_urlopen(url, timeout=timeout, headers=FEED_FETCH_HEADERS) as response:
            status = getattr(response, "status", 200)
            body = response.read()
    except UnsafeURLError as exc:
        msg = f"refused to fetch {url!r}: {exc}"
        raise FeedFetchError(msg) from exc
    except HTTPError as exc:
        msg = f"{url} returned HTTP {exc.code}."
        raise FeedFetchError(msg) from exc
    except (http.client.HTTPException, OSError) as exc:
        # URLError (DNS, connection refused, timeout) subclasses OSError;
        # http.client.HTTPException (e.g. IncompleteRead from a truncated body
        # during response.read()) does not, so catch it explicitly.
        msg = f"could not fetch {url}: {exc}."
        raise FeedFetchError(msg) from exc

    if status is not None and not 200 <= status < 300:
        msg = f"{url} returned HTTP {status}."
        raise FeedFetchError(msg)
    return body


def compare_django_chat_live_feed(
    *,
    source_url: str = RSS_FEED_URL,
    candidate_url: str,
    timeout: float = DEFAULT_FETCH_TIMEOUT,
    copied_byte_sizes_by_guid: dict[str, int] | None = None,
) -> FeedSmokeResult:
    """Fetch both feeds live and run strict parity, returning a report result.

    The candidate enclosure-length truth is the copied object size from the local
    import DB (looked up by :func:`compare_source_to_generated_feed` when
    ``copied_byte_sizes_by_guid`` is ``None``), not the source-reported RSS length.
    """

    try:
        source_bytes = fetch_feed_bytes(source_url, timeout=timeout)
    except FeedFetchError as exc:
        return _fetch_failure_result(
            source_url, candidate_url, f"Source feed could not be read: {exc}"
        )

    try:
        source = parse_rss_feed(source_bytes, source_url=source_url)
    except (ElementTree.ParseError, ValueError) as exc:
        return _fetch_failure_result(
            source_url, candidate_url, f"Source feed could not be parsed as RSS: {exc}."
        )

    try:
        candidate_bytes = fetch_feed_bytes(candidate_url, timeout=timeout)
    except FeedFetchError as exc:
        return _fetch_failure_result(
            source_url, candidate_url, f"Candidate feed could not be read: {exc}"
        )

    try:
        candidate = parse_generated_podcast_feed(candidate_bytes)
    except (ElementTree.ParseError, ValueError) as exc:
        return _fetch_failure_result(
            source_url,
            candidate_url,
            f"Candidate feed could not be parsed as the expected RSS shape: {exc}.",
        )

    return compare_source_to_generated_feed(
        source,
        candidate,
        generated_feed_path=candidate_url,
        copied_byte_sizes_by_guid=copied_byte_sizes_by_guid,
        strict_live_parity=True,
    )


def _fetch_failure_result(source_url: str, candidate_url: str, text: str) -> FeedSmokeResult:
    return FeedSmokeResult(
        source_feed_url=source_url,
        generated_feed_path=candidate_url,
        source_item_count=0,
        generated_item_count=0,
        messages=(FeedSmokeMessage("failure", text),),
    )
