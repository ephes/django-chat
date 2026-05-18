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
def long_transcript_site(tmp_path: Path) -> Iterator[None]:
    with override_settings(MEDIA_ROOT=tmp_path):
        import_django_chat_sample(copy_audio=True, audio_downloader=FakeAudioDownloader())
        episode = Episode.objects.get(slug="django-tasks-jake-howard")
        assert episode.podcast_audio is not None
        _create_generated_transcript(episode.podcast_audio)
        yield


@pytest.fixture
def page_with_long_transcript(long_transcript_site: None) -> Iterator[Page]:
    yield from _playwright_page()


def _playwright_page() -> Iterator[Page]:
    """Create a Playwright page for fixtures with different Django data setup."""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        errors: list[str] = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on(
            "console",
            lambda message: errors.append(message.text) if message.type == "error" else None,
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
def test_player_transcript_tab_uses_single_scroll_container(
    live_server: Any,
    page_with_long_transcript: Page,
) -> None:
    page_with_long_transcript.goto(
        f"{live_server.url}{episode_detail_path('django-tasks-jake-howard')}"
    )
    page_with_long_transcript.locator("[data-django-chat-player-placeholder]").click()
    iframe = page_with_long_transcript.locator("podlove-player iframe").first
    iframe.wait_for(state="attached", timeout=10_000)
    frame = iframe.element_handle().content_frame()
    assert frame is not None
    frame.wait_for_selector("#app.loaded", timeout=15_000)
    frame.evaluate(
        """() => {
            const trigger = Array.from(
                document.querySelectorAll('[data-test="tab-trigger--shownotes"]')
            ).find((node) => {
                const rect = node.getBoundingClientRect();
                return rect.width > 0 && rect.height > 0;
            });
            trigger.click();
        }"""
    )
    frame.wait_for_selector("#tab-shownotes", timeout=10_000)
    frame.evaluate(
        """() => {
            const tab = document.querySelector("#tab-shownotes");
            const spacer = document.createElement("div");
            spacer.textContent = "Long shownotes content";
            spacer.style.height = "900px";
            tab.appendChild(spacer);
        }"""
    )
    frame.wait_for_selector("#tab-shownotes.active", timeout=10_000)

    shownotes_metrics = frame.evaluate(
        """() => {
            const shownotes = document.querySelector("#tab-shownotes");
            const styles = getComputedStyle(shownotes);
            return {
                maxHeight: styles.maxHeight,
                overflowX: styles.overflowX,
                overflowY: styles.overflowY,
                clientHeight: shownotes.clientHeight,
                scrollHeight: shownotes.scrollHeight,
            };
        }"""
    )

    assert shownotes_metrics["maxHeight"] == "420px"
    assert shownotes_metrics["overflowX"] == "hidden"
    assert shownotes_metrics["overflowY"] == "auto"
    assert shownotes_metrics["clientHeight"] <= 420
    assert shownotes_metrics["scrollHeight"] > shownotes_metrics["clientHeight"] + 1

    frame.evaluate(
        """() => {
            const trigger = Array.from(
                document.querySelectorAll('[data-test="tab-trigger--transcripts"]')
            ).find((node) => {
                const rect = node.getBoundingClientRect();
                return rect.width > 0 && rect.height > 0;
            });
            trigger.click();
        }"""
    )
    frame.wait_for_selector('[data-test="tab-transcripts--results"]', timeout=10_000)

    metrics = frame.evaluate(
        """() => {
            const results = document.querySelector('[data-test="tab-transcripts--results"]');
            const transcriptTab = document.querySelector("#tab-transcripts");
            const outer = Array.from(document.querySelectorAll('.w-full.relative')).find(
                (node) => node.querySelector('[data-test="tab-transcripts--results"]')
            );
            const outerStyles = getComputedStyle(outer);
            const resultsStyles = getComputedStyle(results);
            const transcriptTabStyles = getComputedStyle(transcriptTab);
            return {
                outerOverflowY: outerStyles.overflowY,
                outerClientHeight: outer.clientHeight,
                outerScrollHeight: outer.scrollHeight,
                transcriptTabMaxHeight: transcriptTabStyles.maxHeight,
                resultsOverflowX: resultsStyles.overflowX,
                resultsOverflowY: resultsStyles.overflowY,
                resultsClientHeight: results.clientHeight,
                resultsScrollHeight: results.scrollHeight,
            };
        }"""
    )

    assert metrics["outerOverflowY"] == "visible"
    assert metrics["outerScrollHeight"] <= metrics["outerClientHeight"] + 1
    assert metrics["transcriptTabMaxHeight"] == "none"
    assert metrics["resultsOverflowX"] == "hidden"
    assert metrics["resultsOverflowY"] == "auto"
    assert metrics["resultsScrollHeight"] > metrics["resultsClientHeight"] + 1


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


def _create_generated_transcript(audio: Audio) -> Any:
    transcript_model = apps.get_model("cast", "Transcript")
    transcript = transcript_model.objects.create(audio=audio)
    segments = [
        {
            "start": _podlove_time(index * 2_000),
            "start_ms": index * 2_000,
            "end": _podlove_time((index + 1) * 2_000),
            "end_ms": (index + 1) * 2_000,
            "speaker": "Host",
            "voice": "",
            "text": f"Generated transcript segment {index + 1} for scroll testing.",
        }
        for index in range(80)
    ]
    transcript.podlove.save("podlove.json", ContentFile(json.dumps({"transcripts": segments})))
    return transcript


def _podlove_time(milliseconds: int) -> str:
    total_seconds, ms = divmod(milliseconds, 1000)
    minutes, seconds = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{ms:03d}"
