from __future__ import annotations

from typing import Any, cast

from cast.models import Episode, Podcast
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render

from django_chat.imports.models import PodcastSourceMetadata


def podcast_episode_index(request: HttpRequest) -> HttpResponse:
    podcast = get_object_or_404(Podcast.objects.live(), slug="episodes")
    posts = list(Episode.objects.live().child_of(podcast).order_by("-visible_date"))
    for post in posts:
        cast(Any, post).page_url = post.get_url(request=request)

    template_base_dir = podcast.get_template_base_dir(cast(Any, request))
    cast(Any, request).cast_site_template_base_dir = template_base_dir
    canonical_url = request.build_absolute_uri(podcast.get_url(request=request) or request.path)
    source_metadata = (
        PodcastSourceMetadata.objects.filter(podcast=podcast)
        .prefetch_related("source_links")
        .first()
    )

    return render(
        request,
        # The default django-cast podcast index path assumes copied audio; this project
        # template keeps metadata-only sample imports browseable.
        "cast/django_chat/blog_list_of_posts.html",
        {
            "page": podcast,
            "blog": podcast,
            "podcast": podcast,
            "posts": posts,
            "object_list": posts,
            "canonical_url": canonical_url,
            "source_metadata": source_metadata,
            "is_paginated": False,
            "template_base_dir": template_base_dir,
        },
    )
