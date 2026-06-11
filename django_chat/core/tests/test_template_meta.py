from __future__ import annotations

import io
import re
from collections.abc import Callable
from html.parser import HTMLParser
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
    assert '<meta name="theme-color" content="#0d0d0d">' in body
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
def test_share_dialog_url_uses_request_host_not_canonical_site(client: Client) -> None:
    import_django_chat_sample()
    detail = episode_detail_path("django-tasks-jake-howard")

    # The share dialog builds its URL from the request host (the test client's
    # "testserver") rather than the canonical Wagtail Site host, so share links
    # resolve on whatever origin the reader is on — e.g. the dev server's :8000
    # port, which the canonical Site URL omits. No Site is ever "testserver", so
    # the request host appearing here proves the URL is request-based.
    body = client.get(detail).content.decode()
    assert f'data-share-url="http://testserver{detail}"' in body
    assert f'id="share-url-input" data-share-url-input value="http://testserver{detail}"' in body
    # urlencode keeps "/" but encodes ":" — see share-pill hrefs.
    assert f"url=http%3A//testserver{detail}" in body  # twitter / facebook / linkedin
    # Canonical/OG meta stays canonical (Site-based), not switched to the request host.
    assert '<link rel="canonical"' in body


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
def test_episode_index_omits_bootstrap_package_assets(client: Client) -> None:
    import_django_chat_sample()

    response = client.get(episode_index_path())

    body = response.content.decode()
    assert "cast_bootstrap5" not in body
    assert "bootstrap.min.css" not in body
    assert "bootstrap.bundle.min.js" not in body


@pytest.mark.django_db
def test_episode_index_loads_view_transition_script_and_hooks(client: Client) -> None:
    import_django_chat_sample()

    response = client.get(episode_index_path())

    body = response.content.decode()
    assert 'src="/static/django_chat/js/view-transitions.js' in body
    assert 'defer src="/static/django_chat/js/view-transitions.js' in body
    assert 'type="module" src="/static/django_chat/js/view-transitions.js"' not in body
    assert '<link rel="expect" href="#episode-index-main" blocking="render">' in body
    hero_picture_attrs = tag_attrs(body, "picture", {"class": "show-hero-bg"})
    assert hero_picture_attrs is not None
    assert hero_picture_attrs["aria-hidden"] == "true"
    assert "/static/django_chat/img/show-hero-bg.avif 1584w" in body
    hero_image_attrs = tag_attrs(
        body,
        "img",
        {"src": "/static/django_chat/img/show-hero-bg.jpg"},
    )
    assert hero_image_attrs is not None
    assert hero_image_attrs["sizes"] == "100vw"
    assert hero_image_attrs["fetchpriority"] == "high"
    assert hero_image_attrs["decoding"] == "async"
    assert '<div id="episode-index-main" class="page-content" data-vt-page="episode-index">' in body
    filter_form_attrs = tag_attrs(body, "form", {"class": "filter-form"})
    assert filter_form_attrs is not None
    assert filter_form_attrs["id"] == "all-episodes"
    assert filter_form_attrs["aria-label"] == "Filter episodes"
    assert filter_form_attrs["autocomplete"] == "off"
    assert filter_form_attrs["data-vt-transition"] == "filter"
    assert "data-vt-pagination-status" in body
    assert 'class="episode-results" data-vt-results aria-busy="false"' in body
    assert 'class="episode-row" href="/episodes/django-tasks-jake-howard/"' in body
    assert 'data-vt-episode-slug="django-tasks-jake-howard"' in body
    assert "data-vt-episode-badge" in body
    assert "<h2 data-vt-episode-title>Django Tasks - Jake Howard</h2>" in body


@pytest.mark.django_db
def test_episode_detail_exposes_view_transition_episode_hooks(client: Client) -> None:
    import_django_chat_sample()

    response = client.get(episode_detail_path("django-tasks-jake-howard"))

    body = response.content.decode()
    assert '<link rel="expect" href="#episode-detail-main" blocking="render">' in body
    assert 'id="episode-detail-main" class="page-content" data-vt-page="episode-detail"' in body
    assert 'data-vt-episode-slug="django-tasks-jake-howard"' in body
    expected_back_link = (
        'class="back-link" href="/episodes/#all-episodes" '
        'data-vt-episode-slug="django-tasks-jake-howard"'
    )
    assert expected_back_link in body
    assert 'class="episode-number-badge episode-number-badge--detail"' in body
    assert "data-vt-episode-badge" in body
    assert "<h1 data-vt-episode-title>Django Tasks - Jake Howard</h1>" in body


def test_site_css_pins_django_chat_palette() -> None:
    css_path = settings.ROOT_DIR / "django_chat/static/django_chat/css/site.css"
    css = css_path.read_text()
    normalized_css = css.lower()

    assert "@view-transition {\n  navigation: auto;\n}" in css
    assert "@media (prefers-reduced-motion: no-preference)" in css
    assert "@media (prefers-reduced-motion: reduce)" in css
    assert (
        "html:active-view-transition-type(filter)::view-transition-old(dc-episode-results)" in css
    )
    assert "html[data-vt-same-pagination]::view-transition-new(dc-episode-results)" in css
    assert "::view-transition-group(dc-episode-badge)" in css
    assert "::view-transition-group(dc-episode-title)" in css
    assert ".episode-number-badge--detail {" in css
    assert ".audio-panel,\n.audio-panel * {" in css
    assert "background-color: var(--dc-surface-deep);" in _css_blocks(css, "html")[0]
    assert "overflow-x: clip;" in _css_blocks(css, "html")[0]
    assert "--dc-muted: #5f635d;" in css
    assert "--dc-accent: #2d8260;" in css
    assert "--dc-accent-dark: #14513a;" in css
    assert "--dc-django: #0ea342;" in css
    assert "--dc-surface-django-tint: #dfeede;" in css
    assert "--dc-error: #c0392b;" in css
    assert "RobotoFlex-Variable.woff2" not in css
    assert "Roboto Flex" not in css  # dead font fallback retired
    assert '--font-body: "Roboto", system-ui, -apple-system, "Segoe UI", sans-serif;' in css
    assert "background: var(--dc-accent-dark);" in _css_blocks(css, ".button-primary")[0]
    assert "min-height: var(--dc-tap);" in _css_blocks(css, ".button-primary")[0]
    assert ".filter-clear-all {" in css
    assert "background: var(--dc-accent-dark);" in css
    assert ".filter-control-button {" in css
    assert ".filter-date-popover {" in css
    assert ".filter-select-popover {" in css
    assert "font-weight: 900;" in css
    assert ".episode-number-hash {" in css
    assert "fill: var(--dc-django);" in css
    assert ".episode-number-badge span:last-child {" in css
    assert "color: var(--dc-django);" in css
    assert "--episode-badge-size: clamp(4.5rem, 9vw, 9rem);" in css
    assert "grid-template-columns: var(--episode-badge-size) 1fr;" in css
    assert "width: var(--episode-badge-size);" in css
    assert "height: var(--episode-badge-size);" in css
    assert "font-size: clamp(2.25rem, 4.5vw, 4.5rem);" in css
    assert (
        ".button-primary,\n"
        ".platform-band-links a,\n"
        ".feed-action,\n"
        '.filter-form button[type="submit"],\n'
        ".filter-clear-all,\n"
        ".footer-mastodon-button,\n"
        ".share-pill,\n"
        ".pagination-nav a {\n"
        "  display: inline-flex;\n"
        "  align-items: center;\n"
        "  border-radius: var(--dc-radius-pill);\n"
        "  text-decoration: none;\n"
        "}"
    ) in css
    assert ".feed-action--primary:hover,\n.feed-action--primary:focus-visible," in css
    assert "  background: var(--dc-django);\n  border-color: var(--dc-django);" in css
    assert "#0e7c7b" not in normalized_css
    assert "#5d6673" not in normalized_css
    assert "#0d6efd" not in normalized_css
    assert "#6610f2" not in normalized_css
    assert "#0dcaf0" not in normalized_css


def test_topbar_current_nav_link_contrasts_on_dark_surfaces() -> None:
    css_path = settings.ROOT_DIR / "django_chat/static/django_chat/css/site.css"
    css = css_path.read_text()
    current_nav_block = _css_blocks(css, '.nav-links a[aria-current="page"]')[-1]
    current_color = _css_color_value(css, current_nav_block)
    surface_deep = _css_var_hex(css, "--dc-surface-deep")
    stacked_nav_surface = _mix_srgb(surface_deep, "#ffffff", 0.08)

    assert _contrast_ratio(current_color, surface_deep) >= 4.5
    assert _contrast_ratio(current_color, stacked_nav_surface) >= 4.5


@pytest.mark.django_db
def test_episode_detail_uses_svg_logo_when_cover_image_is_imported(
    client: Client,
    tmp_path: Path,
) -> None:
    with override_settings(MEDIA_ROOT=tmp_path):
        import_django_chat_sample(cover_image_downloader=_fake_cover_image_downloader())

        response = client.get(episode_detail_path("django-tasks-jake-howard"))

    body = response.content.decode()
    assert 'class="show-artwork show-artwork--default"' in body, (
        "episode detail hero should use the static SVG logo even when cover_image is imported"
    )
    artwork_html = _html_around(body, 'class="show-artwork show-artwork--default"')
    assert "/static/django_chat/img/django-chat-logo.svg" in artwork_html
    assert "/media/images/" not in artwork_html
    assert 'width="280"' in artwork_html
    assert 'height="256"' in artwork_html


def episode_index_path() -> str:
    return reverse("django_chat_episode_index")


def episode_detail_path(slug: str) -> str:
    return f"/{settings.DJANGO_CHAT_PODCAST_SLUG}/{slug}/"


def tag_attrs(body: str, tag: str, matching_attrs: dict[str, str]) -> dict[str, str] | None:
    parser = TagAttrsParser(tag, matching_attrs)
    parser.feed(body)
    return parser.attrs


class TagAttrsParser(HTMLParser):
    attrs: dict[str, str] | None

    def __init__(self, tag: str, matching_attrs: dict[str, str]) -> None:
        super().__init__()
        self.tag = tag
        self.matching_attrs = matching_attrs
        self.attrs = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = {key: value or "" for key, value in attrs}
        if tag == self.tag and all(
            attrs_dict.get(key) == value for key, value in self.matching_attrs.items()
        ):
            self.attrs = attrs_dict


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


def _css_blocks(css: str, selector: str) -> list[str]:
    blocks = []
    search_from = 0
    while True:
        start = css.find(f"{selector} {{", search_from)
        if start == -1:
            return blocks
        end = css.index("}", start)
        blocks.append(css[start : end + 1])
        search_from = end + 1


def _css_var_hex(css: str, name: str, seen: frozenset[str] = frozenset()) -> str:
    assert name not in seen
    match = re.search(
        rf"{re.escape(name)}:\s*(#[0-9a-fA-F]{{6}}|var\((--[\w-]+)\));",
        css,
    )
    assert match is not None
    if match.group(2):
        return _css_var_hex(css, match.group(2), seen | {name})
    return match.group(1)


def _css_color_value(css: str, block: str) -> str:
    match = re.search(r"\n\s*color:\s*(#[0-9a-fA-F]{6}|var\((--[\w-]+)\));", block)
    assert match is not None
    if match.group(2):
        return _css_var_hex(css, match.group(2))
    return match.group(1)


def _mix_srgb(color_a: str, color_b: str, color_b_weight: float) -> str:
    a_channels = _hex_channels(color_a)
    b_channels = _hex_channels(color_b)
    channels = [
        round(a * (1 - color_b_weight) + b * color_b_weight)
        for a, b in zip(a_channels, b_channels, strict=True)
    ]
    return "#" + "".join(f"{channel:02x}" for channel in channels)


def _contrast_ratio(color_a: str, color_b: str) -> float:
    luminance_a = _relative_luminance(color_a)
    luminance_b = _relative_luminance(color_b)
    lighter = max(luminance_a, luminance_b)
    darker = min(luminance_a, luminance_b)
    return (lighter + 0.05) / (darker + 0.05)


def _relative_luminance(color: str) -> float:
    red, green, blue = [_linear_channel(channel) for channel in _hex_channels(color)]
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def _linear_channel(channel: int) -> float:
    value = channel / 255
    if value <= 0.03928:
        return value / 12.92
    return ((value + 0.055) / 1.055) ** 2.4


def _hex_channels(color: str) -> tuple[int, int, int]:
    return int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
