from __future__ import annotations

from copy import copy
from typing import Any, cast

from cast.feeds import LatestEntriesFeed
from cast.models import Episode, Podcast
from cast.models.repository import FeedContext
from django.db.models import Model
from django.template.loader import render_to_string
from django.utils.safestring import SafeText


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
        post_queryset = (
            Episode.objects.live()
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

    def item_description(self, post: Model) -> SafeText:
        if not isinstance(post, Episode):
            return super().item_description(post)
        assert self.repository is not None

        repository = self.repository.get_post_detail_repository(post)
        context_page = copy(post)
        context_page.owner = post.owner
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
