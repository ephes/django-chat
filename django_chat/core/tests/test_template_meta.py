from __future__ import annotations

import io
from collections.abc import Callable
from pathlib import Path

import pytest
from django.conf import settings
from django.test import Client, override_settings
from django.urls import reverse

from django_chat.imports.import_sample import import_django_chat_sample


@pytest.mark.django_db
def test_episode_index_emits_favicon_links(client: Client) -> None:
    import_django_chat_sample()

    response = client.get(episode_index_path())

    body = response.content.decode()
    assert 'rel="icon"' in body
    assert "favicon.svg" in body
    assert "favicon.ico" in body
    assert "apple-touch-icon" in body


@pytest.mark.django_db
def test_episode_index_emits_og_tags(client: Client) -> None:
    import_django_chat_sample()

    response = client.get(episode_index_path())

    body = response.content.decode()
    assert 'property="og:site_name"' in body
    assert 'property="og:title"' in body
    assert 'property="og:image"' in body
    assert 'property="og:type" content="website"' in body
    assert 'name="twitter:card" content="summary_large_image"' in body


@pytest.mark.django_db
def test_episode_detail_emits_article_og_type(client: Client) -> None:
    import_django_chat_sample()

    response = client.get(episode_detail_path("django-tasks-jake-howard"))

    body = response.content.decode()
    assert 'property="og:type" content="article"' in body


@pytest.mark.django_db
def test_episode_index_loads_self_hosted_fonts_css(client: Client) -> None:
    import_django_chat_sample()

    response = client.get(episode_index_path())

    body = response.content.decode()
    assert "django_chat/css/site.css" in body
    # No third-party Google Fonts request:
    assert "fonts.googleapis.com" not in body
    assert "fonts.gstatic.com" not in body


@pytest.mark.django_db
def test_episode_index_uses_optimized_cover_image_rendition(
    client: Client,
    tmp_path: Path,
) -> None:
    with override_settings(MEDIA_ROOT=tmp_path):
        import_django_chat_sample(cover_image_downloader=_fake_cover_image_downloader())

        response = client.get(episode_index_path())

    body = response.content.decode()
    artwork_html = _html_around(body, 'class="show-artwork"')
    assert "/media/images/" in artwork_html
    assert "fill-560x560" in artwork_html
    assert 'width="560"' in artwork_html
    assert 'height="560"' in artwork_html
    assert 'fetchpriority="high"' in artwork_html


@pytest.mark.django_db
def test_episode_detail_uses_optimized_cover_image_rendition(
    client: Client,
    tmp_path: Path,
) -> None:
    with override_settings(MEDIA_ROOT=tmp_path):
        import_django_chat_sample(cover_image_downloader=_fake_cover_image_downloader())

        response = client.get(episode_detail_path("django-tasks-jake-howard"))

    body = response.content.decode()
    artwork_html = _html_around(body, 'class="show-artwork"')
    assert "/media/images/" in artwork_html
    assert "fill-560x560" in artwork_html
    assert 'width="560"' in artwork_html
    assert 'height="560"' in artwork_html


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


def episode_index_path() -> str:
    return reverse("django_chat_episode_index")


def episode_detail_path(slug: str) -> str:
    return f"/{settings.DJANGO_CHAT_PODCAST_SLUG}/{slug}/"


def _fake_cover_image_downloader() -> Callable[[str], bytes]:
    def download(_source_url: str) -> bytes:
        from PIL import Image as PILImage

        buf = io.BytesIO()
        PILImage.new("RGB", (1200, 1200), color=(0, 0, 0)).save(buf, format="PNG")
        return buf.getvalue()

    return download


def _html_around(body: str, needle: str) -> str:
    index = body.index(needle)
    start = body.rfind("<img", 0, index)
    end = body.find(">", index)
    return body[start : end + 1]
