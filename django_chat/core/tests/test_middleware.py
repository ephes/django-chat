"""Tests for the environment-specific transcript cache-busting middleware."""

from __future__ import annotations

from types import SimpleNamespace

from django.conf import settings
from django.http import HttpResponse
from django.test import Client, RequestFactory, override_settings
from django.urls import include, path, resolve, reverse

from django_chat.core.middleware import (
    _TRANSCRIPT_VIEW_NAME,
    DisableTranscriptCacheMiddleware,
)


def _cacheable_transcript_response(_request: object, pk: int) -> HttpResponse:
    return HttpResponse(
        f"transcript {pk}",
        headers={
            "Cache-Control": "public, max-age=3600",
            "ETag": '"abc"',
            "Last-Modified": "Fri, 04 Sep 2026 12:00:00 GMT",
            "Expires": "Fri, 04 Sep 2026 13:00:00 GMT",
        },
    )


_api_urls = (
    [
        path(
            "audios/<int:pk>/player-transcript/",
            _cacheable_transcript_response,
            name="audio_player_transcript",
        )
    ],
    "api",
)
_cast_urls = ([path("", include(_api_urls, namespace="api"))], "cast")
urlpatterns = [path("api/", include(_cast_urls, namespace="cast"))]


def _run(url: str, headers: dict[str, str], *, view_name: str) -> HttpResponse:
    def get_response(_request: object) -> HttpResponse:
        response = HttpResponse("ok")
        for key, value in headers.items():
            response[key] = value
        return response

    middleware = DisableTranscriptCacheMiddleware(get_response)
    request = RequestFactory().get(url)
    request.resolver_match = SimpleNamespace(view_name=view_name)
    return middleware(request)


def test_player_transcript_response_is_made_uncacheable() -> None:
    response = _run(
        reverse(_TRANSCRIPT_VIEW_NAME, kwargs={"pk": 1}),
        {
            "Cache-Control": "public, max-age=3600",
            "ETag": '"abc"',
            "Last-Modified": "Fri, 04 Sep 2026 12:00:00 GMT",
            "Expires": "Fri, 04 Sep 2026 13:00:00 GMT",
        },
        view_name=_TRANSCRIPT_VIEW_NAME,
    )
    assert "no-store" in response["Cache-Control"]
    assert not response.has_header("ETag")
    assert not response.has_header("Last-Modified")
    assert not response.has_header("Expires")


def test_transcript_view_name_matches_project_urlconf() -> None:
    url = reverse("cast:api:audio_player_transcript", kwargs={"pk": 1})
    assert resolve(url).view_name == _TRANSCRIPT_VIEW_NAME


@override_settings(
    ROOT_URLCONF=__name__,
    MIDDLEWARE=[
        *settings.MIDDLEWARE,
        "django_chat.core.middleware.DisableTranscriptCacheMiddleware",
    ],
)
def test_django_client_applies_middleware_after_url_resolution() -> None:
    response = Client().get("/api/audios/1/player-transcript/")
    assert response.status_code == 200
    assert response["Cache-Control"] == "no-store, no-cache, must-revalidate, max-age=0"
    assert not response.has_header("ETag")
    assert not response.has_header("Last-Modified")
    assert not response.has_header("Expires")


def test_other_paths_keep_their_cache_headers() -> None:
    response = _run(
        "/episodes/django-tasks-jake-howard/",
        {"Cache-Control": "public, max-age=60"},
        view_name="wagtail_serve",
    )
    assert response["Cache-Control"] == "public, max-age=60"


def test_request_without_resolver_match_keeps_cache_headers() -> None:
    def get_response(_request: object) -> HttpResponse:
        return HttpResponse("ok", headers={"Cache-Control": "public, max-age=60"})

    request = RequestFactory().get("/not-found/")
    response = DisableTranscriptCacheMiddleware(get_response)(request)
    assert response["Cache-Control"] == "public, max-age=60"


def test_similarly_named_path_keeps_its_cache_headers() -> None:
    response = _run(
        "/episodes/player-transcript-retrospective/",
        {"Cache-Control": "public, max-age=60", "ETag": '"abc"'},
        view_name="wagtail_serve",
    )
    assert response["Cache-Control"] == "public, max-age=60"
    assert response["ETag"] == '"abc"'
