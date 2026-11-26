"""The one place that decides which podcast page is "Django Chat".

The podcast is the public, live page with slug ``DJANGO_CHAT_PODCAST_SLUG``
directly under the root page of the Wagtail site serving the request, i.e. the
page that answers ``/<slug>/`` on that site. Wagtail keeps sibling slugs
unique, so this names exactly one page. A bare slug lookup does not: another
podcast elsewhere in the page tree (for example a view-restricted one) may
carry the same slug.

The episode index, the embed and sponsor views, and the header context
processor (episode detail pages and the feed page) all resolve the podcast and
its imported source metadata through these helpers. Both are cached on the
request, so a page that needs them in a view and in the context processor
looks them up once.
"""

from __future__ import annotations

from typing import Any

from cast.models import Podcast
from django.conf import settings
from django.db.models import QuerySet
from django.http import HttpRequest
from wagtail.models import Site

_PODCAST_ATTR = "_django_chat_podcast"
_SOURCE_METADATA_ATTR = "_django_chat_source_metadata"


def _podcast_queryset(request: HttpRequest) -> QuerySet | None:
    site = Site.find_for_request(request)
    if site is None:
        return None
    return (
        Podcast.objects.live()
        .public()
        .child_of(site.root_page)
        .filter(slug=settings.DJANGO_CHAT_PODCAST_SLUG)
    )


def get_django_chat_podcast(request: HttpRequest) -> Podcast | None:
    if not hasattr(request, _PODCAST_ATTR):
        queryset = _podcast_queryset(request)
        setattr(request, _PODCAST_ATTR, queryset.first() if queryset is not None else None)
    return getattr(request, _PODCAST_ATTR)


def get_django_chat_source_metadata(request: HttpRequest) -> Any:
    """Return the podcast's source metadata with its links prefetched, or None."""
    if not hasattr(request, _SOURCE_METADATA_ATTR):
        from django_chat.imports.models import PodcastSourceMetadata

        if hasattr(request, _PODCAST_ATTR):
            podcast = getattr(request, _PODCAST_ATTR)
            queryset = PodcastSourceMetadata.objects.filter(podcast=podcast)
        else:
            # Pages that do not need the podcast itself get its metadata in
            # one query, with the podcast lookup as a subquery.
            podcasts = _podcast_queryset(request)
            queryset = (
                PodcastSourceMetadata.objects.filter(podcast__in=podcasts)
                if podcasts is not None
                else PodcastSourceMetadata.objects.none()
            )
        setattr(
            request,
            _SOURCE_METADATA_ATTR,
            queryset.prefetch_related("source_links").first(),
        )
    return getattr(request, _SOURCE_METADATA_ATTR)
