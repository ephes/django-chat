from __future__ import annotations

import json
import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from cast.models import Audio, Episode
from django.apps import apps
from django.core.files.base import ContentFile
from django.test import override_settings
from django.urls import reverse
from playwright.sync_api import Locator, Page, expect, sync_playwright

from django_chat.imports.import_sample import DownloadedAudio, import_django_chat_sample

pytestmark = [
    pytest.mark.browser,
    pytest.mark.skipif(
        os.environ.get("DJANGO_CHAT_BROWSER_TESTS") != "1",
        reason="set DJANGO_CHAT_BROWSER_TESTS=1 or run `just test-browser` to enable browser tests",
    ),
]


@pytest.fixture
def sample_site() -> None:
    import_django_chat_sample()


@pytest.fixture
def page(sample_site: None) -> Iterator[Page]:
    yield from _playwright_page()


@pytest.fixture
def loadable_audio_site(tmp_path: Path) -> Iterator[None]:
    with override_settings(MEDIA_ROOT=tmp_path):
        import_django_chat_sample(copy_audio=True, audio_downloader=FakeAudioDownloader())
        yield


@pytest.fixture
def diarized_custom_player_site(loadable_audio_site: None) -> Iterator[None]:
    """Repository-backed diarized-transcript state for the custom player.

    Creates a multi-speaker transcript with speaker labels that match visible
    ``EpisodeContributor`` records (so they survive sanitization) plus one
    non-contributor label (so its label is stripped) — no reliance on mutable
    dev-DB state. The matching custom-player browser tests prove
    contributor-approved speaker headings, sparse timestamps, and the privacy
    contract.
    """
    episode = Episode.objects.get(slug="django-tasks-jake-howard")
    assert episode.podcast_audio is not None
    _assign_contributor(episode, display_name="Ada Lovelace", slug="ada-lovelace")
    _assign_contributor(episode, display_name="Grace Hopper", slug="grace-hopper")
    _create_diarized_transcript(episode.podcast_audio)
    yield


@pytest.fixture
def page_with_diarized_custom_player(diarized_custom_player_site: None) -> Iterator[Page]:
    # The fake audio bytes cannot decode; ignore the resulting media-load console
    # noise (the transcript/share UI under test does not need playback).
    yield from _playwright_page(ignore_media_errors=True)


@pytest.fixture
def long_title_custom_player_site(diarized_custom_player_site: None) -> Iterator[None]:
    # The episode-204 "How France Ditched Microsoft" shape: wraps to two lines
    # at desktop widths (where the cover is sized to still fit the content)
    # and to three lines at narrow two-column widths (where the content
    # outgrows the cover and the separator hands off to the full-width rule).
    Episode.objects.filter(slug="django-tasks-jake-howard").update(
        title="How France Ditched Microsoft - Samuel Paccoud",
    )
    yield


@pytest.fixture
def page_with_long_title_custom_player(long_title_custom_player_site: None) -> Iterator[Page]:
    yield from _playwright_page(ignore_media_errors=True)


def _is_media_load_error(text: str) -> bool:
    """Benign console noise from the fake (non-decodable) test audio bytes.

    The custom player's <audio> points at the tiny ``FakeAudioDownloader`` bytes,
    which the browser cannot decode — it logs a media-load/format error. That is
    expected in the test harness (the UI under test does not need playback), so it
    must not fail the page-error assertion. Real JS errors still do.
    """
    lowered = text.lower()
    return any(
        token in lowered
        for token in (
            "failed to load because no supported source",
            "media",
            "demuxer",
            "decode",
            "err_",
        )
    )


def _playwright_page(ignore_media_errors: bool = False) -> Iterator[Page]:
    """Create a Playwright page for fixtures with different Django data setup."""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        errors: list[str] = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on(
            "console",
            lambda message: (
                errors.append(message.text)
                if message.type == "error"
                and not (ignore_media_errors and _is_media_load_error(message.text))
                else None
            ),
        )

        yield page

        browser.close()

    assert errors == []


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_filter_form_controls_are_enhanced_and_update_native_fields(
    live_server: Any,
    page: Page,
) -> None:
    page.goto(f"{live_server.url}{episode_index_path()}?date_after=2026-01-01")
    page.locator(".filter-form[data-filter-enhanced='true']").wait_for()

    start_date = page.locator("#id_date_0")
    expect_value(start_date, "2026-01-01")
    assert start_date.get_attribute("aria-hidden") == "true"
    assert start_date.get_attribute("tabindex") == "-1"

    page.get_by_role("button", name="Start date").click()
    page.locator(".filter-date-day[data-date='2026-01-02']").click()

    expect_value(start_date, "2026-01-02")
    assert page.get_by_role("button", name="Start date").inner_text() == "02.01.2026"

    sort_select = page.locator("select[name='o']")
    page.get_by_role("button", name="Sort order").click()
    page.get_by_role("button", name="Date", exact=True).click()

    expect_value(sort_select, "visible_date")
    assert page.get_by_role("button", name="Sort order").inner_text() == "Date"


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_filter_navigation_keeps_replaced_form_enhanced(
    live_server: Any,
    page: Page,
) -> None:
    page.goto(f"{live_server.url}{episode_index_path()}")
    page.locator(".filter-form[data-filter-enhanced='true']").wait_for()
    page.evaluate(
        """() => {
            window.__djangoChatViewTransitionCalls = 0;
            window.__djangoChatViewTransitionReadyTypes = [];
            window.__djangoChatViewTransitionReadyMetrics = [];
            const originalStartViewTransition = document.startViewTransition.bind(document);
            document.startViewTransition = (callback) => {
                const transition = originalStartViewTransition(callback);
                window.__djangoChatViewTransitionCalls += 1;
                transition.ready.then(
                    () => {
                        const results = document.querySelector("[data-vt-results]");
                        const rect = results.getBoundingClientRect();
                        window.__djangoChatViewTransitionReadyTypes.push(
                            Array.from(transition.types || []).join(",")
                        );
                        window.__djangoChatViewTransitionReadyMetrics.push({
                            resultsTop: rect.top,
                            scrollY: window.scrollY,
                            viewportHeight: window.innerHeight,
                        });
                    },
                    () => window.__djangoChatViewTransitionReadyTypes.push("rejected")
                );
                return transition;
            };
        }"""
    )
    page.evaluate(
        """() => document.querySelector(".filter-form").scrollIntoView({
            block: "end",
            inline: "nearest",
        })"""
    )
    page.locator("[data-vt-results]").scroll_into_view_if_needed()
    scroll_before = page.evaluate("window.scrollY")
    assert scroll_before > 0
    page.evaluate("window.__djangoChatSearchPageId = 'before-filter-submit'")

    page.locator("#id_search").fill("tasks")
    page.get_by_role("button", name="Filter").click()
    page.wait_for_function(
        "() => new URL(window.location.href).searchParams.get('search') === 'tasks'"
    )

    # Search/filter submits should stay on the same document so the first
    # visible result-list transition happens where the user submitted the form.
    assert page.evaluate("window.__djangoChatSearchPageId") == "before-filter-submit"
    page.wait_for_function("() => window.__djangoChatViewTransitionReadyTypes.length > 0")
    assert page.evaluate("window.__djangoChatViewTransitionCalls") == 1
    assert page.evaluate("window.__djangoChatViewTransitionReadyTypes[0]") == "filter"
    ready_metrics = page.evaluate("window.__djangoChatViewTransitionReadyMetrics[0]")
    assert ready_metrics["scrollY"] > 0
    assert 0 <= ready_metrics["resultsTop"] < ready_metrics["viewportHeight"]
    page.locator(".filter-form[data-filter-enhanced='true']").wait_for()
    assert page.locator(".filter-date-control").count() == 2
    assert page.locator(".filter-select-control").count() == 2
    assert page.locator(".episode-row").count() == 1
    assert page.get_by_role("heading", name="Django Tasks - Jake Howard").is_visible()

    page.get_by_role("button", name="Start date").click()
    assert page.get_by_role("dialog", name="Choose start date").is_visible()


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_back_to_episodes_restores_scroll_and_clears_remembered_index_state(
    live_server: Any,
    page: Page,
) -> None:
    # Regression test: view-transitions.js must register its pagereveal
    # listener before the first rendering opportunity (classic head script,
    # not defer/async). When the listener loses that race, the inbound index
    # page never restores the remembered scroll position and the one-shot
    # sessionStorage state is never consumed.
    #
    # The race itself is timing-dependent (localhost usually wins it even with
    # defer), so pin the deterministic mechanism: the listener must be added
    # while the document is still parsing. defer/async scripts run at
    # readyState "interactive", after the parser — and after the browser may
    # already have fired pagereveal on slower real-world loads.
    page.add_init_script(
        """
        window.__vtPagerevealListenerReadyState = null;
        const originalAddEventListener = window.addEventListener.bind(window);
        window.addEventListener = function (type, listener, options) {
            if (type === "pagereveal" && window.__vtPagerevealListenerReadyState === null) {
                window.__vtPagerevealListenerReadyState = document.readyState;
            }
            return originalAddEventListener(type, listener, options);
        };
        """
    )
    page.goto(f"{live_server.url}{episode_index_path()}")
    assert page.evaluate("window.__vtPagerevealListenerReadyState") == "loading"
    row = page.locator("a.episode-row").last
    slug = row.get_attribute("data-vt-episode-slug")
    row.scroll_into_view_if_needed()
    scroll_before = page.evaluate("window.scrollY")
    assert scroll_before > 0
    row.click()

    page.locator("[data-vt-page='episode-detail']").wait_for()
    stored = page.evaluate("JSON.parse(sessionStorage.getItem('djangoChatEpisodeIndexUrl'))")
    assert stored["episodeSlug"] == slug
    assert stored["scrollY"] == scroll_before
    # With a recorded scroll position the static #all-episodes fallback hash
    # is dropped so the scroll restore owns the landing position.
    page.wait_for_function("() => !document.querySelector('a.back-link').href.includes('#')")
    page.locator("a.back-link").click()

    page.locator("[data-vt-page='episode-index']").wait_for()
    page.wait_for_function(f"() => Math.abs(window.scrollY - {scroll_before}) < 1")
    assert page.evaluate("sessionStorage.getItem('djangoChatEpisodeIndexUrl')") is None


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_share_rail_button_opens_share_dialog_and_close_button_dismisses_it(
    live_server: Any,
    page: Page,
) -> None:
    page.goto(f"{live_server.url}{episode_detail_path()}")
    dialog = page.locator("#share-dialog")
    expect(dialog).not_to_have_attribute("open", "")

    page.locator('.rail-item[data-action="share"]').click()
    expect(dialog).to_have_attribute("open", "")
    # The URL input is pre-populated with the canonical episode URL —
    # the canonical host can differ from `live_server.url`, so just
    # match the path suffix.
    url_value = dialog.locator("[data-share-url-input]").input_value()
    assert url_value.endswith(episode_detail_path())

    dialog.locator("[data-share-close]").click()
    expect(dialog).not_to_have_attribute("open", "")


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_share_dialog_closes_on_backdrop_click(
    live_server: Any,
    page: Page,
) -> None:
    page.goto(f"{live_server.url}{episode_detail_path()}")
    dialog = page.locator("#share-dialog")

    page.locator('.rail-item[data-action="share"]').click()
    expect(dialog).to_have_attribute("open", "")

    # The dialog's `click` handler closes when `event.target === dialog`
    # itself. Backdrop clicks fire on the dialog element with that target;
    # since `dialog.bounding_box()` returns the inner box, dispatch a
    # synthetic click on the dialog directly to exercise the handler.
    dialog.evaluate("(el) => el.dispatchEvent(new MouseEvent('click', {bubbles: true}))")
    expect(dialog).not_to_have_attribute("open", "")


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_share_start_at_toggle_appends_t_param_to_share_url(
    live_server: Any,
    page: Page,
) -> None:
    page.goto(f"{live_server.url}{episode_detail_path()}")
    page.locator('.rail-item[data-action="share"]').click()

    dialog = page.locator("#share-dialog")
    toggle = dialog.locator("[data-startat-toggle]")
    time_input = dialog.locator("[data-startat-time]")
    url_input = dialog.locator("[data-share-url-input]")

    # Initially the time input is disabled and the URL has no `t` param.
    expect(time_input).to_be_disabled()
    initial = url_input.input_value()
    assert initial.endswith(episode_detail_path())
    assert "t=" not in initial

    toggle.check()
    expect(time_input).to_be_enabled()
    time_input.fill("3:14")

    expect(url_input).to_have_value(f"{initial}?t=194")


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_platform_band_links_layout_invariants_across_viewports(
    live_server: Any,
    page: Page,
) -> None:
    page.goto(f"{live_server.url}{episode_index_path()}")
    page.locator(".platform-band-links a").first.wait_for()

    def measure_rows() -> list[list[dict[str, float]]]:
        return page.evaluate(
            """() => {
                const items = Array.from(document.querySelectorAll('.platform-band-links a'))
                    .map((a) => {
                        const r = a.getBoundingClientRect();
                        return { name: a.textContent.trim(), width: r.width, top: r.top };
                    });
                const rows = new Map();
                for (const item of items) {
                    const key = Math.round(item.top);
                    if (!rows.has(key)) rows.set(key, []);
                    rows.get(key).push(item);
                }
                return [...rows.values()].sort((a, b) => a[0].top - b[0].top);
            }"""
        )

    # Desktop: all seven buttons share one row.
    for width in (1280, 1400):
        page.set_viewport_size({"width": width, "height": 900})
        rows = measure_rows()
        assert len(rows) == 1, f"viewport {width}px expected 1 row, got {len(rows)}"
        assert len(rows[0]) == 7

    # Tablet/laptop / pre-trigger desktop: the last row must never be a
    # single orphan button, including the viewports just below the 1120-px
    # container-query trigger where a 6+1 layout would otherwise creep in.
    for width in (640, 900, 1024, 1080, 1100, 1151):
        page.set_viewport_size({"width": width, "height": 900})
        rows = measure_rows()
        assert len(rows) >= 2, f"viewport {width}px expected wrapping"
        assert len(rows[-1]) >= 2, (
            f"viewport {width}px last row has {len(rows[-1])} button(s); want >= 2"
        )

    # In the viewports where the min-width clamp exceeds every label's
    # natural width, *all* buttons across all rows share one inline-size.
    for width in (900, 1024, 1100, 1151):
        page.set_viewport_size({"width": width, "height": 900})
        rows = measure_rows()
        all_widths = [item["width"] for row in rows for item in row]
        spread = max(all_widths) - min(all_widths)
        assert spread < 1.0, (
            f"viewport {width}px button widths {all_widths} differ (spread {spread:.1f})"
        )

    # Wrapped-state hard cap: an unexpectedly long label must not widen its
    # button beyond the shared clamp; the surplus text truncates via ellipsis.
    page.set_viewport_size({"width": 900, "height": 900})
    baseline = measure_rows()
    baseline_widths: dict[str, float] = {
        str(item["name"]): float(item["width"]) for row in baseline for item in row
    }
    page.evaluate(
        """() => {
            const target = document.querySelector('.platform-band-links a span:last-child');
            target.dataset.originalText = target.textContent;
            target.textContent = 'A Very Long Future Platform Name';
        }"""
    )
    after = measure_rows()
    after_widths = [item["width"] for row in after for item in row]
    spread = max(after_widths) - min(after_widths)
    assert spread < 1.0, (
        f"long label broke equal inline-size: widths {after_widths} (spread {spread:.1f})"
    )
    long_label_width = next(item["width"] for row in after for item in row if item["width"] > 0)
    assert long_label_width == pytest.approx(baseline_widths["YouTube"], abs=1.0), (
        f"long label widened the button to {long_label_width}px; baseline was "
        f"{baseline_widths['YouTube']}px"
    )


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_embed_rail_button_opens_dialog_with_iframe_snippet(
    live_server: Any,
    page: Page,
) -> None:
    page.goto(f"{live_server.url}{episode_detail_path()}")
    dialog = page.locator("#embed-dialog")
    expect(dialog).not_to_have_attribute("open", "")

    page.locator('.rail-item[data-action="embed"]').click()
    expect(dialog).to_have_attribute("open", "")

    snippet = dialog.locator("[data-embed-snippet]")
    value = snippet.input_value()
    assert value.startswith("<iframe")
    assert "/episodes/how-to-learn-django/embed/" in value
    assert 'allow="autoplay"' in value

    dialog.locator("[data-embed-close]").click()
    expect(dialog).not_to_have_attribute("open", "")


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_custom_player_one_share_control_and_demoted_keyboard_pref(
    live_server: Any,
    page_with_diarized_custom_player: Page,
) -> None:
    page = page_with_diarized_custom_player
    page.goto(f"{live_server.url}{episode_detail_path('django-tasks-jake-howard')}")
    page.locator("cast-audio-player .cast-player__transport").wait_for()

    # Exactly one user-facing share control: the sidebar rail item, not the
    # in-transport player button (suppressed via transport_share=False).
    expect(page.locator('.rail-item[data-action="share"]')).to_have_count(1)
    expect(page.locator(".cast-player__share")).to_have_count(0)

    # The ambiguous "Tab cues" text is gone; the preference survives as an
    # icon-only secondary control with its accessible name preserved.
    assert page.get_by_text("Tab cues").count() == 0
    pref = page.locator(".cast-transcript__iconpref")
    expect(pref).to_have_count(1)
    assert pref.get_attribute("aria-label") == "Keyboard-navigable cues"


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_custom_player_transcript_speakers_and_sparse_timestamps(
    live_server: Any,
    page_with_diarized_custom_player: Page,
) -> None:
    page = page_with_diarized_custom_player
    page.goto(f"{live_server.url}{episode_detail_path('django-tasks-jake-howard')}")

    page.locator(".cast-panel__toggle", has_text="Transcript").click()
    page.wait_for_selector(".cast-transcript__cue")

    # Speaker headings render for the visible contributors; the non-contributor
    # label is stripped (privacy contract) and never appears. The heading name
    # span carries the speaker (the heading row also holds the initial chip and
    # the run timestamp); names are uppercased via CSS text-transform, so
    # compare case-insensitively.
    speakers = [
        text.upper() for text in page.locator(".cast-transcript__speaker-name").all_inner_texts()
    ]
    assert "ADA LOVELACE" in speakers
    assert "GRACE HOPPER" in speakers
    cues_text = page.locator(".cast-transcript__cues").inner_text()
    assert "MYSTERY CALLER" not in cues_text.upper()
    # the non-contributor's cue text is still present (only the label is gated)
    assert "I am not a listed contributor." in cues_text

    # Labelled mode: the heading rows carry the timestamps (one per speaker
    # run); the per-cue gutter timestamps are fully hidden.
    cue_count = page.locator(".cast-transcript__cue").count()
    run_starts = page.locator(".cast-transcript__cue.is-run-start").count()
    heading_times = page.locator(".cast-transcript__speaker-time:visible").count()
    gutter_times = page.locator(".cast-transcript__time:visible").count()
    classes = page.locator(".cast-transcript__cues").get_attribute("class") or ""
    assert "cast-transcript__cues--labelled" in classes
    assert gutter_times == 0
    assert 0 < heading_times == run_starts < cue_count

    # Click-to-seek stays per cue even where the timestamp is hidden: the
    # continuation cue is a real button with seek data.
    continuation = page.locator(".cast-transcript__cue:not(.is-run-start)").first
    assert continuation.get_attribute("data-start") is not None


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_custom_player_transcript_shows_loading_busy_state(
    live_server: Any,
    page_with_diarized_custom_player: Page,
) -> None:
    page = page_with_diarized_custom_player
    page.goto(f"{live_server.url}{episode_detail_path('django-tasks-jake-howard')}")

    # Delay the lazy transcript endpoint so the busy state is observable.
    def _slow(route: Any) -> None:
        import time

        time.sleep(0.5)
        route.continue_()

    page.route("**/player-transcript/**", _slow)
    page.locator(".cast-panel__toggle", has_text="Transcript").click()

    spinner = page.locator(".cast-transcript__spinner")
    expect(spinner).to_have_count(1)
    assert page.locator(".cast-panel__scroll").first.get_attribute("aria-busy") == "true"

    page.wait_for_selector(".cast-transcript__cue")
    expect(spinner).to_have_count(0)
    assert page.locator(".cast-panel__scroll").first.get_attribute("aria-busy") in (None, "false")


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_custom_player_site_share_uses_player_current_time(
    live_server: Any,
    page_with_diarized_custom_player: Page,
) -> None:
    page = page_with_diarized_custom_player
    page.goto(f"{live_server.url}{episode_detail_path('django-tasks-jake-howard')}")
    page.locator("cast-audio-player .cast-player__transport").wait_for()

    # Report a 21s playback position. Real seeking needs a Range-capable media
    # host (CloudFront/staging); the test serves non-seekable fake audio, so set
    # the element's reported position to exercise the genuine getShareState() ->
    # share-modal.js path the site owns (the read-only API is unchanged by the
    # transport-share opt-out).
    page.evaluate(
        """() => {
            const a = document.querySelector('cast-audio-player audio');
            Object.defineProperty(a, 'currentTime', { configurable: true, get: () => 21 });
        }"""
    )
    state = page.evaluate("() => document.querySelector('cast-audio-player').getShareState()")
    assert round(state["currentTime"]) == 21

    page.locator('.rail-item[data-action="share"]').click()
    dialog = page.locator("#share-dialog")
    expect(dialog).to_have_attribute("open", "")
    expect(dialog.locator("[data-startat-toggle]")).to_be_checked()
    expect(dialog.locator("[data-startat-time]")).to_have_value("0:21")
    url_value = dialog.locator("[data-share-url-input]").input_value()
    assert url_value.endswith("?t=21")
    twitter_href = (
        dialog.locator('.share-pill[data-share-net="twitter"]').get_attribute("href") or ""
    )
    assert "t%3D21" in twitter_href or "t=21" in twitter_href


HERO_GEOMETRY_SCRIPT = """
() => {
  const hero = document.querySelector('.episode-hero');
  const cover = hero.querySelector('.episode-number-badge--detail');
  const content = hero.querySelector('.episode-hero-content');
  const coverRect = cover.getBoundingClientRect();
  const contentRect = content.getBoundingClientRect();
  return {
    overflowAttr: hero.hasAttribute('data-hero-overflow'),
    contentBorderColor: getComputedStyle(content).borderBottomColor,
    heroBorderStyle: getComputedStyle(hero).borderBottomStyle,
    separatorDelta: (contentRect.y + contentRect.height) - (coverRect.y + coverRect.height),
  };
}
"""


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_closed_hero_separator_lands_on_cover_bottom_for_short_titles(
    live_server: Any,
    page_with_diarized_custom_player: Page,
) -> None:
    # Content shorter than the cover: the column's bottom border lands exactly
    # on the cover's bottom edge (the 1d08d77 min-height anchor).
    page = page_with_diarized_custom_player
    page.goto(f"{live_server.url}{episode_detail_path('django-tasks-jake-howard')}")
    page.locator("cast-audio-player .cast-player__transport").wait_for()
    geometry = page.evaluate(HERO_GEOMETRY_SCRIPT)
    assert geometry["overflowAttr"] is False
    assert geometry["contentBorderColor"] != "rgba(0, 0, 0, 0)"
    assert geometry["heroBorderStyle"] == "none"
    assert abs(geometry["separatorDelta"]) < 1


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_closed_hero_separator_stays_on_cover_bottom_for_two_line_titles(
    live_server: Any,
    page_with_long_title_custom_player: Page,
) -> None:
    # At desktop widths the cover is sized so even a two-line title plus
    # player + transcript header still fits inside it — the separator must
    # land on the cover's bottom edge exactly like for short titles.
    page = page_with_long_title_custom_player
    page.set_viewport_size({"width": 1500, "height": 1100})
    page.goto(f"{live_server.url}{episode_detail_path('django-tasks-jake-howard')}")
    page.locator("cast-audio-player .cast-player__transport").wait_for()
    title_box = page.locator(".episode-hero h1").bounding_box()
    assert title_box is not None
    assert title_box["height"] > 60  # actually wraps to two lines
    geometry = page.evaluate(HERO_GEOMETRY_SCRIPT)
    assert geometry["overflowAttr"] is False
    assert geometry["contentBorderColor"] != "rgba(0, 0, 0, 0)"
    assert geometry["heroBorderStyle"] == "none"
    assert abs(geometry["separatorDelta"]) < 1


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_closed_hero_separator_hands_off_when_content_taller_than_cover(
    live_server: Any,
    page_with_long_title_custom_player: Page,
) -> None:
    # At narrow two-column widths the long title wraps to three lines and the
    # closed content outgrows the cover: the short line must not stick out
    # below the cover — episode-hero.js hands off to the full-width hero
    # rule, the same one the open-transcript state uses.
    page = page_with_long_title_custom_player
    page.set_viewport_size({"width": 1000, "height": 1100})
    page.goto(f"{live_server.url}{episode_detail_path('django-tasks-jake-howard')}")
    page.locator("cast-audio-player .cast-player__transport").wait_for()
    geometry = page.evaluate(HERO_GEOMETRY_SCRIPT)
    assert geometry["overflowAttr"] is True
    assert geometry["contentBorderColor"] == "rgba(0, 0, 0, 0)"
    assert geometry["heroBorderStyle"] == "solid"


HERO_CLOSE_STABILITY_SCRIPT = """
async () => {
  const hero = document.querySelector('.episode-hero');
  const toggle = document.querySelector('.cast-panel__toggle');
  const states = new Set();
  const t0 = performance.now();
  toggle.click();  // fold the open transcript back in
  const below = document.querySelector('.episode-contributors')
    || document.querySelector('.show-notes-title');
  const frames = [];
  await new Promise((resolve) => {
    const tick = () => {
      states.add(JSON.stringify({
        attr: hero.hasAttribute('data-hero-overflow'),
        minH: getComputedStyle(hero.querySelector('.episode-hero-content')).minHeight,
        padB: getComputedStyle(hero).paddingBottom,
      }));
      frames.push({t: performance.now() - t0, y: below.getBoundingClientRect().top});
      if (performance.now() - t0 < 1200) requestAnimationFrame(tick);
      else resolve();
    };
    requestAnimationFrame(tick);
  });
  // Stall-then-snap detector: once the fold's spring has decayed below
  // 0.3px/frame, the page content below the hero must not move again.
  // (Catches discrete end-of-animation cleanup, e.g. a flex row-gap dying
  // with the panel body's display:none.)
  let snapAfterStall = 0;
  let stalled = false;
  for (let i = 1; i < frames.length; i++) {
    const dy = Math.abs(frames[i].y - frames[i - 1].y);
    if (!stalled && frames[i].t > 150 && dy < 0.3) stalled = true;
    else if (stalled) snapAfterStall = Math.max(snapAfterStall, dy);
  }
  return {styleStates: [...states], snapAfterStall};
}
"""


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
@pytest.mark.parametrize("viewport_width", [1500, 1000])
def test_hero_styles_do_not_flip_while_transcript_folds_in(
    live_server: Any,
    page_with_long_title_custom_player: Page,
    viewport_width: int,
) -> None:
    # Regression for the close-animation stutter: data-hero-overflow used to
    # be derived from live geometry, so it flipped (and snapped min-height,
    # hero border and padding) right as the fold-in spring settled. The
    # closed-extent measurement keeps every one of those style inputs
    # constant from the first frame of the close to well past its end —
    # at both the aligned (1500px) and handed-off (1000px) widths.
    page = page_with_long_title_custom_player
    page.set_viewport_size({"width": viewport_width, "height": 1100})
    page.goto(f"{live_server.url}{episode_detail_path('django-tasks-jake-howard')}")
    page.locator(".cast-panel__toggle", has_text="Transcript").click()
    page.wait_for_selector(".cast-transcript__cue")
    page.wait_for_timeout(900)  # open spring settles

    result = page.evaluate(HERO_CLOSE_STABILITY_SCRIPT)
    states = result["styleStates"]
    assert len(states) == 1, f"hero separator styles changed mid-close: {states}"
    # The page below the hero must come to rest with the spring — no late
    # one-frame snap (e.g. the panels row-gap collapsing on display:none).
    assert result["snapAfterStall"] < 1, (
        f"content below hero snapped {result['snapAfterStall']:.2f}px after the close settled"
    )


def episode_index_path() -> str:
    return reverse("django_chat_episode_index")


def episode_detail_path(slug: str = "how-to-learn-django") -> str:
    return f"/episodes/{slug}/"


def expect_value(locator: Locator, value: str) -> None:
    expect(locator).to_have_value(value)


class FakeAudioDownloader:
    def __call__(self, source_url: str) -> DownloadedAudio:
        content = f"fake audio bytes for {source_url}".encode()
        return DownloadedAudio(
            content=content,
            content_type="audio/mpeg",
            content_length=len(content),
            filename="sample.mp3",
        )


def _podlove_time(milliseconds: int) -> str:
    total_seconds, ms = divmod(milliseconds, 1000)
    minutes, seconds = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{ms:03d}"


def _assign_contributor(episode: Episode, *, display_name: str, slug: str) -> Any:
    contributor_model = apps.get_model("cast", "Contributor")
    episode_contributor_model = apps.get_model("cast", "EpisodeContributor")
    contributor = contributor_model.objects.create(
        display_name=display_name, slug=slug, visible=True
    )
    episode_contributor_model.objects.create(
        episode=episode,
        contributor=contributor,
        role=episode_contributor_model.ROLE_HOST,
    )
    return contributor


# Diarized cues: two speaker runs each for the visible contributors (so a run has
# a continuation line whose timestamp is hidden), an Ada run reopening (heading
# repeats on speaker change), and a final non-contributor label that sanitization
# must strip to "".
_DIARIZED_SEGMENTS = (
    ("Ada Lovelace", "Welcome to the show, everyone."),
    ("Ada Lovelace", "Today we dig into background tasks in Django."),
    ("Grace Hopper", "Thanks for having me on."),
    ("Grace Hopper", "It is great to talk about this work."),
    ("Ada Lovelace", "Let us start with the basics."),
    ("Mystery Caller", "I am not a listed contributor."),
)


def _create_diarized_transcript(audio: Audio) -> Any:
    transcript_model = apps.get_model("cast", "Transcript")
    transcript = transcript_model.objects.create(audio=audio)
    segments = [
        {
            "start": _podlove_time(index * 2_000),
            "start_ms": index * 2_000,
            "end": _podlove_time((index + 1) * 2_000),
            "end_ms": (index + 1) * 2_000,
            "speaker": speaker,
            "voice": speaker,
            "text": text,
        }
        for index, (speaker, text) in enumerate(_DIARIZED_SEGMENTS)
    ]
    transcript.podlove.save("podlove.json", ContentFile(json.dumps({"transcripts": segments})))
    return transcript
