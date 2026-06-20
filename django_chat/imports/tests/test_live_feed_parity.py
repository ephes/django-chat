"""Tests for the live Simplecast-vs-candidate feed parity checker.

These never touch the network: HTTP fetches are stubbed by patching
``safe_urlopen``, and the SSRF-refusal tests use literal private/loopback/
metadata IPs (and the ``file://`` scheme) that ``validate_outbound_url`` rejects
locally before any socket is opened.
"""

from __future__ import annotations

from email.message import Message
from io import StringIO
from urllib.error import HTTPError, URLError

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from django_chat.imports.feed_smoke import (
    compare_source_to_generated_feed,
    parse_generated_podcast_feed,
)
from django_chat.imports.live_feed_parity import (
    DEFAULT_FETCH_TIMEOUT,
    FeedFetchError,
    compare_django_chat_live_feed,
    fetch_feed_bytes,
)
from django_chat.imports.source_data import RSS_FEED_URL, parse_rss_feed

SOURCE_NS = (
    'xmlns:atom="http://www.w3.org/2005/Atom" '
    'xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd" '
    'xmlns:content="http://purl.org/rss/1.0/modules/content/"'
)
GENERATED_NS = (
    'xmlns:atom="http://www.w3.org/2005/Atom" '
    'xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd" '
    'xmlns:podcast="https://podcastindex.org/namespace/1.0/"'
)

SOURCE_URL = "https://source.example/rss.xml"
CANDIDATE_URL = "https://candidate.example/episodes/feed/podcast/mp3/rss.xml"

GUID_LATEST = "2c78bb02-8162-44f0-b22d-a188f5bbdb9e"
GUID_OLDER = "608e4ca7-a6b0-4e07-b138-97ad41ef17b1"
PUB_LATEST = "Wed, 15 Apr 2026 08:00:00 +0000"
PUB_OLDER = "Wed, 01 Apr 2026 08:00:00 +0000"


# --- XML builders -----------------------------------------------------------


def _source_item(
    *,
    guid: str,
    title: str,
    pub: str = PUB_LATEST,
    duration: str = "01:17:43",
    episode: int | None = None,
    enclosure_url: str | None = None,
    enclosure_type: str = "audio/mpeg",
    enclosure_length: int | None = None,
) -> str:
    parts = [
        "<item>",
        f'<guid isPermaLink="false">{guid}</guid>',
        f"<title>{title}</title>",
        f"<pubDate>{pub}</pubDate>",
        f"<itunes:duration>{duration}</itunes:duration>",
    ]
    if episode is not None:
        parts.append(f"<itunes:episode>{episode}</itunes:episode>")
    if enclosure_url is not None:
        length_attr = f' length="{enclosure_length}"' if enclosure_length is not None else ""
        parts.append(f'<enclosure url="{enclosure_url}" type="{enclosure_type}"{length_attr} />')
    parts.append("</item>")
    return "".join(parts)


def _source_feed(items: list[str], *, title: str = "Django Chat") -> bytes:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<rss version="2.0" {SOURCE_NS}><channel>'
        f"<title>{title}</title>"
        "<link>https://djangochat.com</link>"
        f'<atom:link rel="self" href="{RSS_FEED_URL}" />'
        f"{''.join(items)}"
        "</channel></rss>"
    ).encode()


def _generated_item(
    *,
    guid: str,
    title: str,
    pub: str = PUB_LATEST,
    duration: str = "01:17:43",
    episode: int | None = None,
    enclosure_url: str | None = None,
    enclosure_type: str = "audio/mpeg",
    enclosure_length: int | None = None,
) -> str:
    parts = [
        "<item>",
        f'<guid isPermaLink="false">{guid}</guid>',
        f"<title>{title}</title>",
        f"<pubDate>{pub}</pubDate>",
        f"<itunes:duration>{duration}</itunes:duration>",
    ]
    if episode is not None:
        parts.append(f"<itunes:episode>{episode}</itunes:episode>")
        parts.append(f"<podcast:episode>{episode}</podcast:episode>")
    if enclosure_url is not None:
        length_attr = f' length="{enclosure_length}"' if enclosure_length is not None else ""
        parts.append(f'<enclosure url="{enclosure_url}" type="{enclosure_type}"{length_attr} />')
    parts.append("</item>")
    return "".join(parts)


def _generated_feed(items: list[str], *, title: str = "Django Chat") -> bytes:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<rss version="2.0" {GENERATED_NS}><channel>'
        f"<title>{title}</title>"
        "<link>https://djangochat.com/episodes/</link>"
        f'<atom:link rel="self" href="{CANDIDATE_URL}" />'
        f"{''.join(items)}"
        "</channel></rss>"
    ).encode()


def _compare(source_bytes: bytes, candidate_bytes: bytes, copied: dict[str, int]):
    return compare_source_to_generated_feed(
        parse_rss_feed(source_bytes),
        parse_generated_podcast_feed(candidate_bytes),
        generated_feed_path=CANDIDATE_URL,
        copied_byte_sizes_by_guid=copied,
        strict_live_parity=True,
    )


def _failure_text(result) -> str:
    return "\n".join(message.text for message in result.failures)


def _warning_text(result) -> str:
    return "\n".join(message.text for message in result.warnings)


# --- HTTP stubbing ----------------------------------------------------------


class _FakeResponse:
    def __init__(self, body: bytes, status: int = 200) -> None:
        self._body = body
        self.status = status

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *exc: object) -> bool:
        return False


def _http_error(url: str, code: int, reason: str) -> HTTPError:
    return HTTPError(url, code, reason, Message(), None)


def _patch_fetch(monkeypatch: pytest.MonkeyPatch, responses: dict[str, bytes | Exception]) -> None:
    def fake(url: str, *, timeout: float, headers: dict[str, str] | None = None):
        result = responses[url]
        if isinstance(result, Exception):
            raise result
        return _FakeResponse(result)

    monkeypatch.setattr("django_chat.imports.live_feed_parity.safe_urlopen", fake)


# --- comparator-level strict parity rules -----------------------------------


def test_strict_parity_passes_for_matching_feeds() -> None:
    source = _source_feed(
        [
            _source_item(
                guid=GUID_LATEST,
                title="Django Tasks - Jake Howard",
                episode=200,
                enclosure_url="https://dts.podtrac.com/redirect.mp3/a.mp3",
                enclosure_length=74615234,
            ),
            _source_item(
                guid=GUID_OLDER,
                title="Older Episode",
                pub=PUB_OLDER,
                episode=199,
                enclosure_url="https://dts.podtrac.com/redirect.mp3/b.mp3",
                enclosure_length=555,
            ),
        ]
    )
    candidate = _generated_feed(
        [
            _generated_item(
                guid=GUID_LATEST,
                title="Django Tasks - Jake Howard",
                episode=200,
                enclosure_url="https://media.djangochat.com/a.mp3",
                enclosure_length=74615234,
            ),
            _generated_item(
                guid=GUID_OLDER,
                title="Older Episode",
                pub=PUB_OLDER,
                episode=199,
                enclosure_url="https://media.djangochat.com/b.mp3",
                enclosure_length=555,
            ),
        ]
    )

    result = _compare(source, candidate, {GUID_LATEST: 74615234, GUID_OLDER: 555})

    assert result.passed is True
    assert result.failures == ()


def test_strict_parity_fails_on_item_count_mismatch() -> None:
    source = _source_feed(
        [
            _source_item(guid=GUID_LATEST, title="Latest"),
            _source_item(guid=GUID_OLDER, title="Older", pub=PUB_OLDER),
        ]
    )
    candidate = _generated_feed([_generated_item(guid=GUID_LATEST, title="Latest")])

    result = _compare(source, candidate, {})

    assert result.passed is False
    assert "item count mismatch" in _failure_text(result)


def test_strict_parity_fails_on_extra_candidate_guid() -> None:
    source = _source_feed([_source_item(guid=GUID_LATEST, title="Latest")])
    candidate = _generated_feed(
        [
            _generated_item(guid=GUID_LATEST, title="Latest"),
            _generated_item(guid="extra-unknown-guid", title="Bogus", pub=PUB_OLDER),
        ]
    )

    result = _compare(source, candidate, {})

    assert result.passed is False
    text = _failure_text(result)
    assert "not present in the live" in text
    assert "extra-unknown-guid" in text


def test_strict_parity_fails_when_latest_source_episode_missing() -> None:
    source = _source_feed(
        [
            _source_item(guid=GUID_LATEST, title="Latest", pub=PUB_LATEST),
            _source_item(guid=GUID_OLDER, title="Older", pub=PUB_OLDER),
        ]
    )
    # Candidate keeps only the older episode; the newest source episode is gone.
    candidate = _generated_feed([_generated_item(guid=GUID_OLDER, title="Older", pub=PUB_OLDER)])

    result = _compare(source, candidate, {})

    assert result.passed is False
    text = _failure_text(result)
    assert "latest source episode" in text
    assert GUID_LATEST in text


def test_strict_parity_reports_missing_non_latest_source_guid() -> None:
    source = _source_feed(
        [
            _source_item(guid=GUID_LATEST, title="Latest", pub=PUB_LATEST),
            _source_item(guid=GUID_OLDER, title="Older", pub=PUB_OLDER),
        ]
    )
    # Candidate keeps the newest but drops an older episode.
    candidate = _generated_feed([_generated_item(guid=GUID_LATEST, title="Latest", pub=PUB_LATEST)])

    result = _compare(source, candidate, {})

    assert result.passed is False
    text = _failure_text(result)
    assert "missing" in text
    assert GUID_OLDER in text
    # The newest episode is present, so the latest-episode failure must not fire.
    assert "latest source episode" not in text


def test_strict_parity_fails_on_guid_order_mismatch() -> None:
    source = _source_feed(
        [
            _source_item(guid=GUID_LATEST, title="Latest", pub=PUB_LATEST),
            _source_item(guid=GUID_OLDER, title="Older", pub=PUB_OLDER),
        ]
    )
    candidate = _generated_feed(
        [
            _generated_item(guid=GUID_OLDER, title="Older", pub=PUB_OLDER),
            _generated_item(guid=GUID_LATEST, title="Latest", pub=PUB_LATEST),
        ]
    )

    result = _compare(source, candidate, {})

    assert result.passed is False
    assert "GUID order mismatch" in _failure_text(result)


def test_strict_parity_normalizes_title_whitespace() -> None:
    source = _source_feed([_source_item(guid=GUID_LATEST, title="Django   Tasks  -  Jake Howard ")])
    candidate = _generated_feed(
        [_generated_item(guid=GUID_LATEST, title="Django Tasks - Jake Howard")]
    )

    result = _compare(source, candidate, {})

    assert result.passed is True
    assert "title" not in _failure_text(result)


def test_strict_parity_fails_on_real_title_difference() -> None:
    source = _source_feed([_source_item(guid=GUID_LATEST, title="Django Tasks - Jake Howard")])
    candidate = _generated_feed(
        [_generated_item(guid=GUID_LATEST, title="Django Tasks - Jane Howard")]
    )

    result = _compare(source, candidate, {})

    assert result.passed is False
    assert "title mismatch" in _failure_text(result)


def test_strict_parity_fails_on_enclosure_type_mismatch() -> None:
    source = _source_feed(
        [
            _source_item(
                guid=GUID_LATEST,
                title="Latest",
                enclosure_url="https://src/a.mp3",
                enclosure_type="audio/mpeg",
                enclosure_length=100,
            )
        ]
    )
    candidate = _generated_feed(
        [
            _generated_item(
                guid=GUID_LATEST,
                title="Latest",
                enclosure_url="https://media/a.m4a",
                enclosure_type="audio/x-m4a",
                enclosure_length=100,
            )
        ]
    )

    result = _compare(source, candidate, {GUID_LATEST: 100})

    assert result.passed is False
    assert "enclosure type mismatch" in _failure_text(result)


def test_strict_parity_fails_on_copied_length_mismatch() -> None:
    source = _source_feed(
        [
            _source_item(
                guid=GUID_LATEST,
                title="Latest",
                enclosure_url="https://src/a.mp3",
                enclosure_length=123,
            )
        ]
    )
    candidate = _generated_feed(
        [
            _generated_item(
                guid=GUID_LATEST,
                title="Latest",
                enclosure_url="https://media/a.mp3",
                enclosure_length=999,
            )
        ]
    )

    result = _compare(source, candidate, {GUID_LATEST: 123})

    assert result.passed is False
    text = _failure_text(result)
    assert "enclosure copied length mismatch" in text
    assert "generated=999" in text


def test_strict_parity_warns_on_moved_enclosure_url() -> None:
    source = _source_feed(
        [
            _source_item(
                guid=GUID_LATEST,
                title="Latest",
                enclosure_url="https://dts.podtrac.com/a.mp3",
                enclosure_length=100,
            )
        ]
    )
    candidate = _generated_feed(
        [
            _generated_item(
                guid=GUID_LATEST,
                title="Latest",
                enclosure_url="https://media.djangochat.com/a.mp3",
                enclosure_length=100,
            )
        ]
    )

    result = _compare(source, candidate, {GUID_LATEST: 100})

    assert result.passed is True
    assert "Generated enclosure URLs differ" in _warning_text(result)


def test_strict_parity_warns_on_source_reported_length_difference() -> None:
    source = _source_feed(
        [
            _source_item(
                guid=GUID_LATEST,
                title="Latest",
                enclosure_url="https://src/a.mp3",
                enclosure_length=100,
            )
        ]
    )
    candidate = _generated_feed(
        [
            _generated_item(
                guid=GUID_LATEST,
                title="Latest",
                enclosure_url="https://media/a.mp3",
                enclosure_length=123,
            )
        ]
    )

    # Copied object truth equals the generated length, so the only difference is
    # the source-reported RSS length: an approved warning, not a failure.
    result = _compare(source, candidate, {GUID_LATEST: 123})

    assert result.passed is True
    assert "Strict length checking uses copied bytes" in _warning_text(result)


def test_strict_parity_accepts_equivalent_duration_formatting() -> None:
    source = _source_feed([_source_item(guid=GUID_LATEST, title="Latest", duration="1:17:43")])
    candidate = _generated_feed(
        [_generated_item(guid=GUID_LATEST, title="Latest", duration="01:17:43")]
    )

    result = _compare(source, candidate, {})

    assert result.passed is True
    assert "duration" not in _failure_text(result)


def test_default_mode_does_not_apply_strict_guid_set_checks() -> None:
    # Backward compatibility: existing callers (strict_live_parity defaults False)
    # must not gain the parity-only extra/missing-GUID failures.
    source = parse_rss_feed(_source_feed([_source_item(guid=GUID_LATEST, title="Latest")]))
    candidate = parse_generated_podcast_feed(
        _generated_feed(
            [
                _generated_item(guid=GUID_LATEST, title="Latest"),
                _generated_item(guid="extra-unknown-guid", title="Bogus", pub=PUB_OLDER),
            ]
        )
    )

    result = compare_source_to_generated_feed(
        source,
        candidate,
        generated_feed_path=CANDIDATE_URL,
        copied_byte_sizes_by_guid={},
    )

    assert "not present in the live" not in _failure_text(result)


# --- live-fetch helper ------------------------------------------------------


def test_fetch_feed_bytes_returns_body_on_success(monkeypatch: pytest.MonkeyPatch) -> None:
    body = _source_feed([_source_item(guid=GUID_LATEST, title="Latest")])
    _patch_fetch(monkeypatch, {SOURCE_URL: body})

    assert fetch_feed_bytes(SOURCE_URL, timeout=DEFAULT_FETCH_TIMEOUT) == body


def test_fetch_feed_bytes_raises_on_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_fetch(monkeypatch, {CANDIDATE_URL: _http_error(CANDIDATE_URL, 503, "Down")})

    with pytest.raises(FeedFetchError, match="503"):
        fetch_feed_bytes(CANDIDATE_URL, timeout=DEFAULT_FETCH_TIMEOUT)


def test_fetch_feed_bytes_raises_on_url_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_fetch(monkeypatch, {CANDIDATE_URL: URLError("connection refused")})

    with pytest.raises(FeedFetchError):
        fetch_feed_bytes(CANDIDATE_URL, timeout=DEFAULT_FETCH_TIMEOUT)


def test_fetch_feed_bytes_wraps_read_time_http_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    # A truncated body raises http.client.IncompleteRead from response.read();
    # it is an HTTPException, not an OSError, so it must still be wrapped.
    import http.client

    class _BrokenResponse:
        status = 200

        def read(self) -> bytes:
            raise http.client.IncompleteRead(b"partial")

        def __enter__(self) -> _BrokenResponse:
            return self

        def __exit__(self, *exc: object) -> bool:
            return False

    monkeypatch.setattr(
        "django_chat.imports.live_feed_parity.safe_urlopen",
        lambda url, *, timeout, headers=None: _BrokenResponse(),
    )

    with pytest.raises(FeedFetchError):
        fetch_feed_bytes(CANDIDATE_URL, timeout=DEFAULT_FETCH_TIMEOUT)


@pytest.mark.parametrize(
    "url",
    [
        "http://169.254.169.254/latest/meta-data/",
        "http://127.0.0.1:8000/episodes/feed/podcast/mp3/rss.xml",
        "http://10.0.0.5/internal/rss.xml",
        "file:///etc/passwd",
    ],
)
def test_fetch_feed_bytes_refuses_unsafe_urls(url: str) -> None:
    # Real SSRF guard; literal private/loopback/metadata IPs and the file scheme
    # are refused by validate_outbound_url before any socket is opened.
    with pytest.raises(FeedFetchError, match="refus"):
        fetch_feed_bytes(url, timeout=DEFAULT_FETCH_TIMEOUT)


# --- orchestration ----------------------------------------------------------


def test_compare_live_feed_passes_for_matching_feeds(monkeypatch: pytest.MonkeyPatch) -> None:
    source = _source_feed(
        [
            _source_item(
                guid=GUID_LATEST,
                title="Django Tasks - Jake Howard",
                enclosure_url="https://src/a.mp3",
                enclosure_length=100,
            )
        ]
    )
    candidate = _generated_feed(
        [
            _generated_item(
                guid=GUID_LATEST,
                title="Django Tasks - Jake Howard",
                enclosure_url="https://media/a.mp3",
                enclosure_length=100,
            )
        ]
    )
    _patch_fetch(monkeypatch, {SOURCE_URL: source, CANDIDATE_URL: candidate})

    result = compare_django_chat_live_feed(
        source_url=SOURCE_URL,
        candidate_url=CANDIDATE_URL,
        copied_byte_sizes_by_guid={GUID_LATEST: 100},
    )

    assert result.passed is True
    assert result.source_feed_url == RSS_FEED_URL
    assert result.generated_feed_path == CANDIDATE_URL


def test_compare_live_feed_reports_source_ssrf_refusal() -> None:
    # No network: both URLs resolve to non-public addresses, refused locally.
    result = compare_django_chat_live_feed(
        source_url="http://169.254.169.254/latest/meta-data/",
        candidate_url="http://127.0.0.1/rss.xml",
    )

    assert result.passed is False
    text = _failure_text(result)
    assert "refus" in text
    assert "169.254.169.254" in text


def test_compare_live_feed_fails_on_non_200_candidate(monkeypatch: pytest.MonkeyPatch) -> None:
    source = _source_feed([_source_item(guid=GUID_LATEST, title="Latest")])
    _patch_fetch(
        monkeypatch,
        {SOURCE_URL: source, CANDIDATE_URL: _http_error(CANDIDATE_URL, 502, "Bad Gateway")},
    )

    result = compare_django_chat_live_feed(source_url=SOURCE_URL, candidate_url=CANDIDATE_URL)

    assert result.passed is False
    assert "502" in _failure_text(result)


def test_compare_live_feed_fails_on_unparseable_candidate(monkeypatch: pytest.MonkeyPatch) -> None:
    source = _source_feed([_source_item(guid=GUID_LATEST, title="Latest")])
    _patch_fetch(monkeypatch, {SOURCE_URL: source, CANDIDATE_URL: b"not xml at all"})

    result = compare_django_chat_live_feed(source_url=SOURCE_URL, candidate_url=CANDIDATE_URL)

    assert result.passed is False
    assert "parse" in _failure_text(result).lower()


def test_compare_live_feed_surfaces_parity_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    source = _source_feed(
        [
            _source_item(guid=GUID_LATEST, title="Latest", pub=PUB_LATEST),
            _source_item(guid=GUID_OLDER, title="Older", pub=PUB_OLDER),
        ]
    )
    candidate = _generated_feed([_generated_item(guid=GUID_OLDER, title="Older", pub=PUB_OLDER)])
    _patch_fetch(monkeypatch, {SOURCE_URL: source, CANDIDATE_URL: candidate})

    result = compare_django_chat_live_feed(
        source_url=SOURCE_URL,
        candidate_url=CANDIDATE_URL,
        copied_byte_sizes_by_guid={},
    )

    assert result.passed is False
    assert "latest source episode" in _failure_text(result)


# --- management command -----------------------------------------------------


@pytest.mark.django_db
def test_command_prints_report_and_passes(monkeypatch: pytest.MonkeyPatch) -> None:
    source = _source_feed([_source_item(guid=GUID_LATEST, title="Latest")])
    candidate = _generated_feed([_generated_item(guid=GUID_LATEST, title="Latest")])
    _patch_fetch(monkeypatch, {SOURCE_URL: source, CANDIDATE_URL: candidate})
    stdout = StringIO()

    call_command(
        "compare_django_chat_live_feed",
        f"--candidate-url={CANDIDATE_URL}",
        f"--source-url={SOURCE_URL}",
        stdout=stdout,
    )

    assert "PASS" in stdout.getvalue()


@pytest.mark.django_db
def test_command_fails_nonzero_on_parity_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    source = _source_feed(
        [
            _source_item(guid=GUID_LATEST, title="Latest", pub=PUB_LATEST),
            _source_item(guid=GUID_OLDER, title="Older", pub=PUB_OLDER),
        ]
    )
    candidate = _generated_feed([_generated_item(guid=GUID_OLDER, title="Older", pub=PUB_OLDER)])
    _patch_fetch(monkeypatch, {SOURCE_URL: source, CANDIDATE_URL: candidate})
    stdout = StringIO()

    with pytest.raises(CommandError, match="live feed parity check failed"):
        call_command(
            "compare_django_chat_live_feed",
            f"--candidate-url={CANDIDATE_URL}",
            f"--source-url={SOURCE_URL}",
            stdout=stdout,
        )

    assert "FAIL" in stdout.getvalue()


def test_command_requires_candidate_url() -> None:
    with pytest.raises(CommandError):
        call_command("compare_django_chat_live_feed")
