from __future__ import annotations

import pytest
from django.test import Client

from django_chat.imports.import_sample import import_django_chat_sample


@pytest.mark.django_db
def test_episode_index_emits_favicon_links(client: Client) -> None:
    import_django_chat_sample()

    response = client.get("/episodes/")

    body = response.content.decode()
    assert 'rel="icon"' in body
    assert "favicon.svg" in body
    assert "favicon.ico" in body
    assert "apple-touch-icon" in body


@pytest.mark.django_db
def test_episode_index_emits_og_tags(client: Client) -> None:
    import_django_chat_sample()

    response = client.get("/episodes/")

    body = response.content.decode()
    assert 'property="og:site_name"' in body
    assert 'property="og:title"' in body
    assert 'property="og:image"' in body
    assert 'property="og:type" content="website"' in body
    assert 'name="twitter:card" content="summary_large_image"' in body


@pytest.mark.django_db
def test_episode_detail_emits_article_og_type(client: Client) -> None:
    import_django_chat_sample()

    response = client.get("/episodes/django-tasks-jake-howard/")

    body = response.content.decode()
    assert 'property="og:type" content="article"' in body


@pytest.mark.django_db
def test_episode_index_loads_self_hosted_fonts_css(client: Client) -> None:
    import_django_chat_sample()

    response = client.get("/episodes/")

    body = response.content.decode()
    assert "django_chat/css/site.css" in body
    # No third-party Google Fonts request:
    assert "fonts.googleapis.com" not in body
    assert "fonts.gstatic.com" not in body
