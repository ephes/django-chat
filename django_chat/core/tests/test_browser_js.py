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

    page.locator("#id_search").fill("tasks")
    page.get_by_role("button", name="Filter").click()
    page.wait_for_function(
        "() => new URL(window.location.href).searchParams.get('search') === 'tasks'"
    )

    page.locator(".filter-form[data-filter-enhanced='true']").wait_for()
    assert page.locator(".filter-date-control").count() == 2
    assert page.locator(".filter-select-control").count() == 2
    assert page.locator(".episode-row").count() == 1
    assert page.get_by_role("heading", name="Django Tasks - Jake Howard").is_visible()

    page.get_by_role("button", name="Start date").click()
    assert page.get_by_role("dialog", name="Choose start date").is_visible()


def episode_index_path() -> str:
    return reverse("django_chat_episode_index")


def expect_value(locator: Locator, value: str) -> None:
    expect(locator).to_have_value(value)
