from __future__ import annotations

import pytest
from cast.models import Episode, Podcast
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse
from django.utils import timezone
from wagtail.models import Page

from django_chat.core.apps import PODCAST_ADMIN_DEFAULT_ORDERING
from django_chat.imports.import_sample import import_django_chat_sample


@pytest.mark.django_db
def test_podcast_explorer_defaults_to_episode_publish_date_order(client: Client) -> None:
    import_django_chat_sample()
    podcast = Podcast.objects.get(slug=settings.DJANGO_CHAT_PODCAST_SLUG)
    preview = Episode.objects.get(slug="preview")
    user = get_user_model().objects.create_superuser(
        username="admin",
        email="admin@example.com",
        password="password",
    )
    client.force_login(user)

    Page.objects.filter(pk=preview.pk).update(latest_revision_created_at=timezone.now())
    response = client.get(reverse("wagtailadmin_explore", args=[podcast.pk]))

    assert response.status_code == 200
    assert response.context["ordering"] == PODCAST_ADMIN_DEFAULT_ORDERING
    assert [page.slug for page in response.context["pages"][:3]] == [
        "django-tasks-jake-howard",
        "boost-your-github-dx-adam-johnson",
        "pycon-us-2026-elaine-wong-jon-banafato",
    ]
