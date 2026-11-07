"""Guards for outbound HTTP fetches performed by the import pipeline.

The importers fetch URLs that are taken from *remote* responses (Simplecast API
``href`` fields, RSS enclosures, the Podlove ``data-url`` embedded in a staging
episode page). A compromised, typo-squatted, or MITM'd upstream can therefore
steer those fetches at the deployment host's local files (``file://``) or at
internal/cloud-metadata endpoints (SSRF). ``urllib.request.urlopen`` happily
honours ``file://`` and any host, so every default fetcher validates its target
through :func:`validate_outbound_url` first.
"""

from __future__ import annotations

import hashlib
import http.client
import ipaddress
import socket
from email.message import Message
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import (
    HTTPHandler,
    HTTPRedirectHandler,
    HTTPSHandler,
    Request,
    build_opener,
)

ALLOWED_SCHEMES = frozenset({"http", "https"})


class UnsafeURLError(ValueError):
    """Raised when an outbound fetch target is not a safe public http(s) URL."""


def safe_url_label(url: str) -> str:
    """Bounded correlation identifier; no URL components or credentials escape."""
    return "url-sha256:" + hashlib.sha256(url.encode("utf-8", errors="replace")).hexdigest()[:12]


def _is_disallowed_address(host: str) -> bool:
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError:
        # Unresolvable host: let the actual fetch fail with its own error
        # rather than masking a genuine connectivity problem as a safety error.
        return False
    for info in infos:
        address = str(info[4][0])
        try:
            ip = ipaddress.ip_address(address.split("%", 1)[0])
        except ValueError:
            continue
        # `is_global` is False for every non-public range — private, loopback,
        # link-local, reserved, multicast, unspecified, plus CGNAT
        # (100.64.0.0/10), benchmarking, and documentation ranges that the
        # individual flags miss. Reject anything that isn't globally routable.
        if not ip.is_global:
            return True
    return False


def validate_outbound_url(url: str) -> str:
    """Return ``url`` unchanged if it is a safe public http(s) target.

    Rejects non-http(s) schemes (notably ``file://``) and hosts that resolve to
    private, loopback, link-local, reserved, multicast, or unspecified
    addresses (notably the cloud metadata endpoint ``169.254.169.254``).
    """
    try:
        parsed = urlparse(url)
        host = parsed.hostname
    except ValueError:
        raise UnsafeURLError(f"refusing malformed URL ({safe_url_label(url)})") from None
    if parsed.scheme.lower() not in ALLOWED_SCHEMES:
        msg = f"refusing to fetch non-http(s) URL ({safe_url_label(url)})"
        raise UnsafeURLError(msg)
    if not host:
        msg = f"refusing to fetch URL without a host ({safe_url_label(url)})"
        raise UnsafeURLError(msg)
    if _is_disallowed_address(host):
        msg = f"refusing to fetch URL resolving to a non-public address ({safe_url_label(url)})"
        raise UnsafeURLError(msg)
    return url


def _resolve_global_ip(host: str, port: int | None) -> str:
    """Resolve ``host`` and return one address, raising unless EVERY resolved
    address is globally routable.

    This runs at connection time (inside the pinned connection below), so the
    address we validate is the address we connect to — closing the DNS-rebinding
    TOCTOU where a hostname resolves to a public IP during pre-validation but to
    an internal IP at connect time.
    """
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except OSError as exc:
        msg = f"could not resolve host ({safe_url_label(host)})"
        raise UnsafeURLError(msg) from exc
    addresses: list[str] = []
    for info in infos:
        address = str(info[4][0])
        try:
            ip = ipaddress.ip_address(address.split("%", 1)[0])
        except ValueError:
            continue
        if not ip.is_global:
            msg = f"host resolved to a non-public address ({safe_url_label(host)})"
            raise UnsafeURLError(msg)
        addresses.append(address)
    if not addresses:
        msg = f"could not resolve host to a usable address ({safe_url_label(host)})"
        raise UnsafeURLError(msg)
    return addresses[0]


def _pinned_create_connection(
    address: tuple[str, int],
    timeout: Any = None,
    source_address: Any = None,
) -> socket.socket:
    host, port = address
    pinned_ip = _resolve_global_ip(host, port)
    return socket.create_connection((pinned_ip, port), timeout, source_address)


class _PinnedHTTPConnection(http.client.HTTPConnection):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        # HTTPConnection.connect() calls self._create_connection((host, port), …);
        # routing it through our validator pins the socket to a vetted IP while
        # the request's Host header keeps the original hostname.
        self._create_connection = _pinned_create_connection  # type: ignore[method-assign]


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        # HTTPSConnection.connect() defers the raw socket to the inherited
        # HTTPConnection.connect(), then wraps it with TLS using SNI/cert
        # hostname = self.host (unchanged), so certificate validation is intact.
        self._create_connection = _pinned_create_connection  # type: ignore[method-assign]


class _PinnedHTTPHandler(HTTPHandler):
    def http_open(self, req: Request) -> Any:
        return self.do_open(_PinnedHTTPConnection, req)


class _PinnedHTTPSHandler(HTTPSHandler):
    def https_open(self, req: Request) -> Any:
        # Mirror stdlib HTTPSHandler.https_open: pass only the SSL context.
        # HTTPSHandler.__init__ already folds `check_hostname` into that context,
        # and http.client.HTTPSConnection (Python 3.12+) no longer accepts a
        # `check_hostname` kwarg — passing it raises TypeError on every fetch.
        # `_context` is set by HTTPSHandler.__init__ but is not in typeshed.
        return self.do_open(
            _PinnedHTTPSConnection,
            req,
            context=getattr(self, "_context", None),
        )


class _ValidatingRedirectHandler(HTTPRedirectHandler):
    """Re-validate every redirect target so a public host cannot 30x the fetch
    to ``file://`` or an internal/metadata address after passing the initial
    check. urllib's default handler already blocks non-http(s) redirect schemes;
    this adds the private-address check, and the redirect's own fetch is pinned
    by the connection handlers above."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[override]
        validate_outbound_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def safe_urlopen(
    url: str,
    *,
    timeout: float,
    headers: dict[str, str] | None = None,
) -> Any:
    """Validate ``url`` (and any redirect it triggers) before opening it, and
    pin the connection to a validated globally-routable IP.

    Use this instead of :func:`urllib.request.urlopen` for every fetch whose
    target is derived from untrusted (remote) data. The initial
    :func:`validate_outbound_url` call rejects non-http(s) schemes before the
    opener's default ``file://`` handler could ever run.
    """
    validate_outbound_url(url)
    opener = build_opener(
        _PinnedHTTPHandler(),
        _PinnedHTTPSHandler(),
        _ValidatingRedirectHandler(),
    )
    request = Request(url, headers=headers or {})
    try:
        return opener.open(request, timeout=timeout)
    except UnsafeURLError:
        raise
    except HTTPError as exc:
        exc.close()
        raise HTTPError(
            safe_url_label(url), exc.code, "HTTP fetch failed", Message(), None
        ) from None
    except OSError, ValueError, http.client.HTTPException:
        raise OSError(f"HTTP fetch failed ({safe_url_label(url)})") from None
