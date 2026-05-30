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
    assert ".audio-panel,\n.audio-panel *,\npodlove-player,\npodlove-player * {" in css
    assert "background-color: var(--dc-surface-deep);" in _css_blocks(css, "html")[0]
    assert "overflow-x: clip;" in _css_blocks(css, "html")[0]
    assert "--dc-muted: #5f635d;" in css
    assert "--dc-accent: #2d8260;" in css
    assert "--dc-accent-dark: #14513a;" in css
    assert "--dc-django: #0ea342;" in css
    assert "--dc-surface-django-tint: #dfeede;" in css
    assert "--dc-error: #c0392b;" in css
    assert "--dc-player-surface: transparent;" in css
    assert (
        ".audio-panel podlove-player[data-template] .podlove-hover-placeholder {\n"
        "  align-items: start;\n"
        "  background: var(--dc-player-surface);"
    ) in css
    assert (
        ".audio-panel podlove-player[data-template] .podlove-player-container iframe {\n"
        "  /* Podlove's custom element injects light iframe backgrounds after this stylesheet. */\n"
        "  background: var(--dc-player-surface) !important;"
    ) in css
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
        'podlove-player[data-django-chat-player-ready="true"] '
        "[data-django-chat-player-placeholder]" in css
    )
    ready_container_blocks = _css_blocks(
        css,
        '.audio-panel podlove-player[data-django-chat-player-ready="true"] '
        ".podlove-player-container",
    )
    assert len(ready_container_blocks) == 1
    assert "min-height: 0;" in ready_container_blocks[0]
    assert "position: relative;" in ready_container_blocks[0]
    assert "opacity: 0;" not in ready_container_blocks[0]
    assert not re.search(r"(?<!min-)height: 112px !important;", css)
    assert not re.search(r"(?<!min-)height: 168px !important;", css)
    # Player sizing now reserves on the .audio-panel wrapper, not on
    # <podlove-player>. Make sure the wrapper picks up the reserve only
    # when a player actually exists (no hollow reserve for the
    # "Audio copy pending" fallback).
    assert ".audio-panel {\n  --player-min-height: 112px;" in css
    assert ".audio-panel {\n    --player-min-height: 168px;\n  }" in css
    assert ".audio-panel:has(podlove-player) {\n  min-height: var(--player-min-height);" in css
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
    current_color = _css_color_value(current_nav_block)
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
    # Keep the native Podlove chrome tokens dark. The expanded tab panel is
    # restyled from the same-origin iframe hook so changing these tokens does
    # not accidentally alter the play button/progress controls.
    assert tokens["brandDarkest"] == "#14513a"
    # Secondary player chrome should stay neutral rather than slate-blue.
    assert tokens["shadeDark"] == "#5f635d"
    assert tokens["shadeBase"] == "#5f635d"
    # Contrast pinned to the project ink token.
    assert tokens["contrast"] == "#0d0d0d"
    # Podlove's native tab text token stays valid for the default dark panel;
    # the iframe hook overrides transcript/readability styling for this site.
    assert tokens["alt"] == "#ffffff"


@pytest.mark.django_db
def test_podlove_player_template_endpoint_renders_compact_template(client: Client) -> None:
    response = client.get(reverse("django_chat_podlove_player_template"))

    assert response.status_code == 200
    body = response.content.decode()
    assert "<root" in body
    assert "<play-button" in body
    assert "<progress-bar" in body
    assert "<timer-duration" in body
    assert '<tab-trigger tab="shownotes"' in body
    assert '<tab-trigger tab="chapters"' in body
    assert '<tab-trigger tab="transcripts">' in body
    assert "<tab-transcripts></tab-transcripts>" in body
    assert '<tab-trigger tab="share">' not in body
    assert "<tab-share></tab-share>" not in body
    assert '<div class="w-full relative">' in body
    assert "overflow-auto" not in body
    assert "max-height:420px" not in body
    # The wrapper must stay visually neutral when no tab is open. Panel chrome
    # is injected into Podlove's same-origin iframe after the player loads.
    assert "<style" not in body
    assert "dc-player-tabs" not in body
    assert "#e6f0dc" not in body
    assert "border-radius:16px" not in body


def test_podlove_loader_injects_iframe_panel_styles() -> None:
    loader_path = settings.ROOT_DIR / "django_chat/static/django_chat/js/podlove-loader.js"
    loader = loader_path.read_text()

    assert 'const playerPanelStyleId = "django-chat-player-panel-style";' in loader
    assert 'style.setAttribute("data-django-chat-player-style", "");' in loader
    assert "installPlayerPanelStyles(iframeDocument);" in loader
    assert '[data-test="tab"] {' in loader
    assert "background: #e6f0dc !important;" in loader
    assert '[data-test="tab"]:not(#tab-transcripts) {' in loader
    assert "max-height: 420px !important;" in loader
    assert "#tab-transcripts {" in loader
    assert "max-height: none !important;" in loader
    assert '[data-test="tab-title--close"] {' in loader
    assert '[data-test="tab"] [data-test="tab-title--close"] {' in loader
    assert '[data-test="tab-title--close"] svg {' in loader
    assert "stroke-width: 3 !important;" in loader
    assert '[data-test="tab-transcripts--follow"] {' in loader
    assert '[data-test="tab"] [data-test="tab-transcripts--follow"] {' in loader
    assert '[data-test="tab-transcripts--results"] {' in loader
    assert "overflow-x: hidden !important;" in loader
    assert "overflow-y: auto !important;" in loader
    assert '[data-test="divider"] {' in loader
    assert "background: #d8d8d8 !important;" in loader
    assert "background-image: none !important;" in loader
    assert '[data-test="play-button"]:focus-visible {' in loader
    assert '[data-test="play-button"]:focus:not(:focus-visible) {' in loader
    assert 'button#play-button--restart [data-test="play-button--label"] {' in loader
    assert "button#play-button--restart > .wrapper > span {" in loader
    assert (
        'const replayButtonA11yObserverAttribute = "data-django-chat-replay-a11y-observer";'
        in loader
    )
    assert 'restartButton.setAttribute("aria-label", "Replay");' in loader
    assert 'restartButton.setAttribute("title", "Replay");' in loader
    assert '[data-test^="tab-trigger--"]:focus-visible,' in loader
    assert '[data-test^="tab-trigger--"][aria-selected="true"] {' in loader
    assert '[data-test^="tab-trigger--"]:focus:not(:focus-visible) {' in loader
    assert '[data-test="play-button"]:focus,' not in loader
    assert '[data-test^="tab-trigger--"]:focus,' not in loader
    assert "border-radius: 999px !important;" in loader
    assert "border-radius: 8px !important;" in loader
    assert "box-shadow: 0 0 0 2px #0ea342 !important;" in loader
    assert "outline: none !important;" in loader
    assert "Podlove renders the selected-tab marker as the final direct span child." in loader
    assert '[data-test^="tab-trigger--"][aria-selected="true"] > span:last-child,' in loader
    assert "fill: #0ea342 !important;" in loader
    assert '[data-test="tab-transcripts--results"] .active-transcript {' in loader
    assert "background: linear-gradient(to top, rgb(14 163 66 / 0.28)" in loader


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


def _css_var_hex(css: str, name: str) -> str:
    match = re.search(rf"{re.escape(name)}:\s*(#[0-9a-fA-F]{{6}});", css)
    assert match is not None
    return match.group(1)


def _css_color_value(block: str) -> str:
    match = re.search(r"\n\s*color:\s*(#[0-9a-fA-F]{6});", block)
    assert match is not None
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
