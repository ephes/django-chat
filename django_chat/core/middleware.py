"""Environment-specific middleware helpers."""

from __future__ import annotations

from collections.abc import Callable

from django.http import HttpRequest, HttpResponse

# Resolved name of the custom player's lazy transcript endpoint
# (``/api/audios/<pk>/player-transcript/``).
_TRANSCRIPT_VIEW_NAME = "cast:api:audio_player_transcript"


class DisableTranscriptCacheMiddleware:
    """Strip the player-transcript endpoint's long-lived browser cache.

    The custom-player transcript endpoint sends
    ``Cache-Control: public, max-age=3600``. That can hide freshly generated or
    edited speaker labels behind a one-hour browser cache.

    Local development always enables this middleware. Deployed environments
    can opt in with ``DJANGO_CHAT_DISABLE_TRANSCRIPT_CACHE``; staging does so
    because it is where transcript generation and speaker review happen. A
    browser that already cached the old long-lived response still needs one
    hard refresh; subsequent page loads stay fresh.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        response = self.get_response(request)
        resolver_match = getattr(request, "resolver_match", None)
        if getattr(resolver_match, "view_name", None) == _TRANSCRIPT_VIEW_NAME:
            response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            # Drop validators so the browser cannot serve a 304 from a stale entry.
            for header in ("ETag", "Last-Modified", "Expires"):
                if response.has_header(header):
                    del response[header]
        return response
