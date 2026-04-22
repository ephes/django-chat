from __future__ import annotations

from typing import Any

from django.db import DatabaseError
from django.http import HttpRequest


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
    return {"source_metadata": source_metadata}


def _needs_django_chat_source_metadata(path: str) -> bool:
    if path == "/episodes/":
        return True
    if not path.startswith("/episodes/"):
        return False
    return not (
        path.startswith("/episodes/feed/")
        or path.endswith("/transcript/")
        or path.endswith("/twitter-player/")
    )
