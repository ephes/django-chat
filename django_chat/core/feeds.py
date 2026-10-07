from __future__ import annotations

from collections.abc import Callable
from copy import copy
from functools import wraps
from typing import Any, cast
from uuid import uuid4

from cast.feeds import LatestEntriesFeed
from cast.models import Episode, Podcast, Post
from cast.models.repository import FeedContext
from django.core.cache import cache
from django.http import HttpRequest, HttpResponseBase
from django.template.loader import render_to_string
from django.utils.safestring import SafeText
from django.views.decorators.cache import cache_page

FEED_CACHE_GENERATION_KEY = "django_chat:feed-cache-generation"


def feed_cache_generation() -> str:
    """Return the current feed cache generation, creating one if it is missing.

    A view restriction change clears the cache (see
    ``django_chat.core.receivers``), which drops this key; the next request
    then starts a new random generation.
    """
    generation = cache.get(FEED_CACHE_GENERATION_KEY)
    if generation is None:
        candidate = uuid4().hex
        cache.add(FEED_CACHE_GENERATION_KEY, candidate, timeout=None)
        generation = cache.get(FEED_CACHE_GENERATION_KEY) or candidate
    return str(generation)


def restriction_aware_cache_page(
    timeout: int,
) -> Callable[[Callable[..., HttpResponseBase]], Callable[..., HttpResponseBase]]:
    """``cache_page`` whose key prefix is read once, when the request starts.

    A render that was already running when a view restriction changed finishes
    under the old generation, so its stale response is stored where no later
    request looks for it.
    """

    def decorator(view: Callable[..., HttpResponseBase]) -> Callable[..., HttpResponseBase]:
        @wraps(view)
        def cached_view(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponseBase:
            key_prefix = f"django-chat-feed-{feed_cache_generation()}"
            return cache_page(timeout, key_prefix=key_prefix)(view)(request, *args, **kwargs)

        return cached_view

    return decorator


class DjangoChatLatestEntriesFeed(LatestEntriesFeed):
    """Latest-entries feed optimized for Django Chat's episode-only catalog."""

    def get_repository(self, request, blog) -> FeedContext:
        if self.repository is not None and not self.repository.used:
            return self.repository

        podcast = Podcast.objects.filter(pk=blog.pk).first()
        if podcast is None:
            return super().get_repository(request, blog)

        # Matches django-cast's feed repository construction; the page object can be stale.
        podcast.refresh_from_db()
        # `.public()` keeps login-, password- and group-restricted episodes out
        # of the feed, matching django-cast's own feed querysets.
        post_queryset = (
            Episode.objects.live()
            .public()
            .descendant_of(podcast)
            .select_related("podcast_audio__transcript")
            .filter(podcast_audio__isnull=False)
            .order_by("-visible_date")
        )
        return FeedContext.create_from_django_models(
            request=request,
            blog=podcast,
            post_queryset=post_queryset,
        )

    def item_description(self, item: Post) -> SafeText:
        if not isinstance(item, Episode):
            return super().item_description(item)
        assert self.repository is not None

        repository = self.repository.get_post_detail_repository(item)
        context_page = copy(item)
        context_page.owner = item.owner
        # Mirrors django-cast's dynamic page_url convention used by feed rendering.
        cast(Any, context_page).page_url = repository.absolute_page_url
        context = {
            "page": context_page,
            "self": context_page,
            "blog": repository.blog,
            "podcast": repository.blog,
            "comments_are_enabled": repository.comments_are_enabled,
            "render_detail": True,
            "render_for_feed": True,
            "repository": repository,
        }
        description = render_to_string(
            f"cast/{repository.template_base_dir}/post_body.html",
            context=context,
            request=self.request,
        ).replace("\n", "")
        return cast(SafeText, description)
