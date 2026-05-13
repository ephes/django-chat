from __future__ import annotations

import os
from collections.abc import Iterator
from typing import Any

import pytest
from django.urls import reverse
from playwright.sync_api import Locator, Page, expect, sync_playwright

from django_chat.imports.import_sample import import_django_chat_sample

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


def episode_index_path() -> str:
    return reverse("django_chat_episode_index")


def episode_detail_path(slug: str = "how-to-learn-django") -> str:
    return f"/episodes/{slug}/"


def expect_value(locator: Locator, value: str) -> None:
    expect(locator).to_have_value(value)
