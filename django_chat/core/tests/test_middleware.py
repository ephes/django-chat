"""Tests for the dev-only transcript cache-busting middleware."""

from __future__ import annotations

from django.http import HttpResponse
from django.test import RequestFactory

from django_chat.core.middleware import DisableTranscriptCacheMiddleware


def _run(path: str, headers: dict[str, str]) -> HttpResponse:
    def get_response(_request: object) -> HttpResponse:
        response = HttpResponse("ok")
        for key, value in headers.items():
            response[key] = value
        return response

    middleware = DisableTranscriptCacheMiddleware(get_response)
    return middleware(RequestFactory().get(path))


def test_player_transcript_response_is_made_uncacheable() -> None:
    response = _run(
        "/api/audios/1/player-transcript/",
        {"Cache-Control": "public, max-age=3600", "ETag": '"abc"'},
    )
    assert "no-store" in response["Cache-Control"]
    assert not response.has_header("ETag")


def test_other_paths_keep_their_cache_headers() -> None:
    response = _run("/episodes/django-tasks-jake-howard/", {"Cache-Control": "public, max-age=60"})
    assert response["Cache-Control"] == "public, max-age=60"
