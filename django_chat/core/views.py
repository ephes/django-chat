from __future__ import annotations

from typing import Any
from typing import cast as type_cast

from cast.filters import PostFilterset
from cast.models import Episode, Podcast
from django.conf import settings
from django.core.paginator import Paginator
from django.http import HttpRequest, HttpResponse, QueryDict
from django.shortcuts import get_object_or_404, render
from django.views.decorators.clickjacking import xframe_options_exempt

from django_chat.imports.models import PodcastSourceMetadata

EPISODES_PER_PAGE = 20


def active_filter_parameters(request: HttpRequest) -> QueryDict:
    parameters = request.GET.copy()
    parameters.pop("page", None)
    for key in list(parameters):
        values = [value for value in parameters.getlist(key) if value]
        if values:
            parameters.setlist(key, values)
        else:
            parameters.pop(key, None)
    return parameters


def podlove_player_template(request: HttpRequest) -> HttpResponse:
    return render(request, "cast/django_chat/player_template.html", {})


@xframe_options_exempt
def episode_embed(request: HttpRequest, episode_slug: str) -> HttpResponse:
    """Minimal player-only view suitable for `<iframe>` embedding on third-party sites."""
    podcast = get_object_or_404(Podcast.objects.live(), slug=settings.DJANGO_CHAT_PODCAST_SLUG)
    episode = get_object_or_404(Episode.objects.live().child_of(podcast), slug=episode_slug)
    template_base_dir = podcast.get_template_base_dir(type_cast(Any, request))
    type_cast(Any, request).cast_site_template_base_dir = template_base_dir
    return render(
        request,
        "cast/django_chat/episode_embed.html",
        {
            "episode": episode,
            "page": episode,
            "podcast": podcast,
            "template_base_dir": template_base_dir,
        },
    )


def podcast_episode_index(request: HttpRequest) -> HttpResponse:
    podcast = get_object_or_404(Podcast.objects.live(), slug=settings.DJANGO_CHAT_PODCAST_SLUG)

    base_qs = Episode.objects.live().child_of(podcast).order_by("-visible_date")
    filterset = PostFilterset(data=request.GET, queryset=base_qs)
    filtered_qs = filterset.qs

    paginator = Paginator(filtered_qs, EPISODES_PER_PAGE)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    posts = list(page_obj.object_list)
    for post in posts:
        type_cast(Any, post).page_url = post.get_url(request=request)

    parameters = active_filter_parameters(request)
    parameters_querystring = parameters.urlencode()
    parameters_suffix = "&" + parameters_querystring if parameters_querystring else ""

    clear_search_parameters = parameters.copy()
    clear_search_parameters.pop("search", None)
    clear_search_querystring = clear_search_parameters.urlencode()
    clear_search_url = request.path
    if clear_search_querystring:
        clear_search_url = f"{clear_search_url}?{clear_search_querystring}"

    template_base_dir = podcast.get_template_base_dir(type_cast(Any, request))
    type_cast(Any, request).cast_site_template_base_dir = template_base_dir
    canonical_url = request.build_absolute_uri(podcast.get_url(request=request) or request.path)
    source_metadata = (
        PodcastSourceMetadata.objects.filter(podcast=podcast)
        .prefetch_related("source_links")
        .first()
    )

    previous_page_number = page_obj.previous_page_number() if page_obj.has_previous() else None
    next_page_number = page_obj.next_page_number() if page_obj.has_next() else None

    return render(
        request,
        "cast/django_chat/blog_list_of_posts.html",
        {
            "page": podcast,
            "blog": podcast,
            "podcast": podcast,
            "posts": posts,
            "object_list": posts,
            "page_obj": page_obj,
            "paginator": paginator,
            "is_paginated": page_obj.has_other_pages(),
            "page_number": page_obj.number,
            "has_previous": page_obj.has_previous(),
            "previous_page_number": previous_page_number,
            "has_next": page_obj.has_next(),
            "next_page_number": next_page_number,
            "parameters": parameters_suffix,
            "has_filters": bool(parameters_querystring),
            "clear_search_url": clear_search_url,
            "filterset": filterset,
            "canonical_url": canonical_url,
            "source_metadata": source_metadata,
            "template_base_dir": template_base_dir,
        },
    )
