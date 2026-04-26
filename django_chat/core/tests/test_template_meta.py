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


@pytest.mark.django_db
def test_podlove_player_config_uses_django_chat_brand_colors(client: Client) -> None:
    import_django_chat_sample()

    # template_base_dir=django_chat selects the project's theme override
    response = client.get("/api/audios/player_config/?template_base_dir=django_chat")

    assert response.status_code == 200
    config = response.json()
    tokens = config["theme"]["tokens"]
    # Brand colour is in the Django green family (darker than the show
    # artwork mark itself, so white text reaches WCAG AA contrast on
    # brand-coloured player chrome).
    assert tokens["brand"] == "#2d8260"
    # The Podlove default orange must NOT bleed through:
    assert tokens["brand"] != "#E64415"
    # Contrast pinned to the project ink token.
    assert tokens["contrast"] == "#0d0d0d"
