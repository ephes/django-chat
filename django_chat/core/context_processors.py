from __future__ import annotations

from typing import Any

from django.db import DatabaseError
from django.http import HttpRequest

FEED_DETAIL_META_TITLE = "Listen & Subscribe"
FEED_DETAIL_META_DESCRIPTION = (
    "Subscribe to Django Chat through the self-hosted podcast RSS feed or "
    "imported podcast platform links."
)


def django_chat_source_metadata(_request: HttpRequest) -> dict[str, Any]:
    if not _needs_django_chat_source_metadata(_request.path_info):
        return {"source_metadata": None}

    try:
        from django_chat.imports.models import PodcastSourceMetadata

        source_metadata = (
            PodcastSourceMetadata.objects.filter(podcast__slug="episodes")
            .prefetch_related("source_links")
            .first()
        )
    except DatabaseError:
        source_metadata = None

    context: dict[str, Any] = {"source_metadata": source_metadata}
    if _is_django_chat_feed_detail_path(_request.path_info):
        context.update(
            {
                "meta_title": FEED_DETAIL_META_TITLE,
                "meta_description": FEED_DETAIL_META_DESCRIPTION,
            }
        )
    return context


def _needs_django_chat_source_metadata(path: str) -> bool:
    if _is_django_chat_feed_detail_path(path):
        return True
    if path == "/episodes/":
        return True
    if not path.startswith("/episodes/"):
        return False
    return not (
        path.startswith("/episodes/feed/")
        or path.endswith("/transcript/")
        or path.endswith("/twitter-player/")
    )


def _is_django_chat_feed_detail_path(path: str) -> bool:
    return path in {"/episodes/feed", "/episodes/feed/"}
