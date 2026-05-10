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
    assert '<html lang="en" data-theme="light">' in body
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


def test_site_css_pins_green_accent_palette() -> None:
    css_path = settings.ROOT_DIR / "django_chat/static/django_chat/css/site.css"
    css = css_path.read_text()
    normalized_css = css.lower()

    assert "--dc-link: #14513a;" in css
    assert "--dc-muted: #5f635d;" in css
    assert "--dc-django: #65a65c;" in css
    assert "--bs-primary: #2d8260;" in css
    assert "--bs-info: #65a65c;" in css
    assert "--bs-link-color: #14513a;" in css
    assert 'font-family: "Roboto Flex";' in css
    assert "font-stretch: 25% 151%;" in css
    assert ".button-primary {\n  background: var(--dc-accent-dark);" in css
    assert ".button-secondary {\n  background: var(--dc-accent-dark);" in css
    assert ".filter-form button {\n  min-height: 40px;" in css
    assert "background: var(--dc-accent-dark);" in css
    assert ".filter-form button:hover,\n.filter-form button:focus {" in css
    assert 'font-variation-settings: "wdth" 25, "opsz" 30;' in css
    assert "font-weight: 900;" in css
    assert ".episode-number-badge span:first-child {" in css
    assert "color: var(--dc-django);" in css
    assert ".episode-number-badge span:last-child {" in css
    assert "font-size: 1.42em;" in css
    assert "margin-top: -0.74em;" in css
    assert ".rss-primary-link {\n  display: inline-flex;" in css
    assert (
        ".rss-primary-link:hover,\n.rss-primary-link:focus {\n  background: var(--dc-django);"
        in css
    )
    assert "#0e7c7b" not in normalized_css
    assert "#5d6673" not in normalized_css
    assert "#0d6efd" not in normalized_css
    assert "#6610f2" not in normalized_css
    assert "#0dcaf0" not in normalized_css


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
    # Used by Podlove for light chrome and the play-button glyph; keep it
    # opaque so the icon stays visible on the green play button.
    assert tokens["brandLightest"] == "#ffffff"
    # The darkest brand token should stay in the green family so compact
    # player chrome does not fall back to the untinted default strip.
    assert tokens["brandDarkest"] == "#14513a"
    # Secondary player chrome should stay neutral rather than slate-blue.
    assert tokens["shadeDark"] == "#5f635d"
    assert tokens["shadeBase"] == "#5f635d"
    # Contrast pinned to the project ink token.
    assert tokens["contrast"] == "#0d0d0d"


@pytest.mark.django_db
def test_podlove_player_template_endpoint_renders_compact_template(client: Client) -> None:
    response = client.get(reverse("django_chat_podlove_player_template"))

    assert response.status_code == 200
    body = response.content.decode()
    assert "<root" in body
    assert "<play-button" in body
    assert "<progress-bar" in body
    assert '<tab-trigger tab="shownotes">' in body
    assert '<tab-trigger tab="chapters">' in body
    assert '<tab-trigger tab="transcripts">' in body
    assert "<tab-transcripts></tab-transcripts>" in body
    assert '<tab-trigger tab="share">' in body


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
