"""Development-only middleware helpers."""

from __future__ import annotations

from collections.abc import Callable

from django.http import HttpRequest, HttpResponse

# Path fragment of the custom player's lazy transcript endpoint
# (``/api/audios/<pk>/player-transcript/``).
_TRANSCRIPT_PATH_MARKER = "player-transcript"


class DisableTranscriptCacheMiddleware:
    """Strip the player-transcript endpoint's long-lived browser cache in dev.

    The custom-player transcript endpoint sends
    ``Cache-Control: public, max-age=3600`` (correct for production: the cues are
    public and stable). In local development that hides freshly seeded or edited
    transcript data behind a one-hour browser cache, so re-running
    ``seed_django_chat_diarized_demo`` (or re-importing) does not visibly change
    the panel until the cache expires.

    Enabled only from ``config.settings.local``, this middleware rewrites the
    response to ``no-store`` for that endpoint so seeded changes appear on the
    next page load. Do not enable it in production — the production cache is
    intentional. (A browser that already cached the long-lived response still
    needs one hard refresh to drop that entry; afterwards it stays fresh.)
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        response = self.get_response(request)
        if _TRANSCRIPT_PATH_MARKER in request.path:
            response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            # Drop the validator so the browser cannot serve a 304 from a stale entry.
            if response.has_header("ETag"):
                del response["ETag"]
        return response
