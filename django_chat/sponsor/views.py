"""View that exposes the singleton SponsorPage under the podcast slug.

The page lives under the Wagtail home page (root_page) for editor convenience,
but the public URL must sit under the podcast namespace (``/episodes/sponsor/``)
so it parallels the existing ``/episodes/feed/`` subscribe page. Wagtail's
default routing would have served it at ``/sponsor/``, so we proxy here.
"""

from __future__ import annotations

from typing import Any
from typing import cast as type_cast

from cast.models import Podcast
from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404

from django_chat.sponsor.models import SponsorPage


def sponsor_page(request: HttpRequest) -> HttpResponse:
    page = get_object_or_404(SponsorPage.objects.live().specific())
    podcast = Podcast.objects.live().filter(slug=settings.DJANGO_CHAT_PODCAST_SLUG).first()
    if podcast is not None:
        template_base_dir = podcast.get_template_base_dir(type_cast(Any, request))
        type_cast(Any, request).cast_site_template_base_dir = template_base_dir
    return page.serve(request)
