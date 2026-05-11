from __future__ import annotations

from html.parser import HTMLParser

import pytest
from django.test import Client
from django.urls import reverse

from django_chat.imports.import_sample import import_django_chat_sample


@pytest.mark.django_db
def test_episode_index_filters_by_search_query(client: Client) -> None:
    import_django_chat_sample()

    response = client.get(f"{episode_index_path()}?search=tasks")

    assert response.status_code == 200
    body = response.content.decode()
    assert "Django Tasks - Jake Howard" in body
    assert "How to Learn Django" not in body


@pytest.mark.django_db
def test_episode_index_unfiltered_lists_all_sample_episodes(client: Client) -> None:
    import_django_chat_sample()

    response = client.get(episode_index_path())

    assert response.status_code == 200
    body = response.content.decode()
    assert "Django Tasks - Jake Howard" in body
    assert "How to Learn Django" in body


@pytest.mark.django_db
def test_episode_index_exposes_filterset_form_fields(client: Client) -> None:
    import_django_chat_sample()

    response = client.get(episode_index_path())

    body = response.content.decode()
    form_attrs = tag_attrs(body, "form", {"class": "filter-form"})
    assert form_attrs is not None
    assert form_attrs["method"] == "get"
    assert form_attrs["aria-label"] == "Filter episodes"
    assert form_attrs["autocomplete"] == "off"
    assert form_attrs["data-vt-transition"] == "filter"
    search_attrs = tag_attrs(body, "input", {"name": "search"})
    assert search_attrs is not None
    assert search_attrs["type"] == "text"
    assert search_attrs["placeholder"] == "Search episodes"
    assert search_attrs["value"] == ""
    assert search_attrs["autocomplete"] == "off"
    start_date_attrs = tag_attrs(body, "input", {"name": "date_after"})
    assert start_date_attrs is not None
    assert start_date_attrs["id"] == "id_date_0"
    assert start_date_attrs["value"] == ""
    assert start_date_attrs["autocomplete"] == "off"
    end_date_attrs = tag_attrs(body, "input", {"name": "date_before"})
    assert end_date_attrs is not None
    assert end_date_attrs["id"] == "id_date_1"
    assert end_date_attrs["value"] == ""
    assert end_date_attrs["autocomplete"] == "off"
    assert '<label class="visually-hidden" for="id_date_0">Start date</label>' in body
    assert '<label class="visually-hidden" for="id_date_1">End date</label>' in body
    date_facets_attrs = tag_attrs(body, "select", {"name": "date_facets"})
    assert date_facets_attrs is not None
    assert date_facets_attrs["aria-label"] == "Date facets"
    assert date_facets_attrs["autocomplete"] == "off"
    ordering_attrs = tag_attrs(body, "select", {"name": "o"})
    assert ordering_attrs is not None
    assert ordering_attrs["aria-label"] == "Sort order"
    assert ordering_attrs["autocomplete"] == "off"


@pytest.mark.django_db
def test_episode_index_omits_clear_search_link_without_search_query(client: Client) -> None:
    import_django_chat_sample()

    response = client.get(episode_index_path())

    body = response.content.decode()
    assert clear_search_link_attrs(body) is None
    assert clear_filters_link_attrs(body) is None


@pytest.mark.django_db
def test_episode_index_ignores_empty_search_filter_state(client: Client) -> None:
    import_django_chat_sample()

    response = client.get(f"{episode_index_path()}?search=")

    body = response.content.decode()
    assert clear_search_link_attrs(body) is None
    assert clear_filters_link_attrs(body) is None
    assert response.context["parameters"] == ""
    assert response.context["has_filters"] is False


@pytest.mark.django_db
def test_episode_index_ignores_empty_filter_form_values(client: Client) -> None:
    import_django_chat_sample()

    response = client.get(
        f"{episode_index_path()}?search=&date_after=&date_before=&date_facets=&o="
    )

    body = response.content.decode()
    assert clear_search_link_attrs(body) is None
    assert clear_filters_link_attrs(body) is None
    assert response.context["parameters"] == ""
    assert response.context["has_filters"] is False


@pytest.mark.django_db
def test_episode_index_clear_search_link_removes_only_search_query(client: Client) -> None:
    import_django_chat_sample()

    response = client.get(
        f"{episode_index_path()}?search=tasks&date_after=2026-01-01&o=visible_date&page=2"
    )

    body = response.content.decode()
    attrs = clear_search_link_attrs(body)
    assert attrs is not None
    assert attrs["aria-label"] == "Clear search"
    assert attrs["data-vt-transition"] == "filter"
    assert attrs["href"] == "/episodes/?date_after=2026-01-01&o=visible_date"

    clear_attrs = clear_filters_link_attrs(body)
    assert clear_attrs is not None
    assert clear_attrs["data-vt-transition"] == "filter"
    assert clear_attrs["href"] == "/episodes/"


@pytest.mark.django_db
def test_episode_index_clear_search_link_drops_to_index_without_other_filters(
    client: Client,
) -> None:
    import_django_chat_sample()

    response = client.get(f"{episode_index_path()}?search=tasks")

    body = response.content.decode()
    attrs = clear_search_link_attrs(body)
    assert attrs is not None
    assert attrs["href"] == "/episodes/"


@pytest.mark.django_db
def test_episode_index_clear_search_link_drops_empty_sibling_filters(
    client: Client,
) -> None:
    import_django_chat_sample()

    response = client.get(
        f"{episode_index_path()}?search=tasks&date_after=&date_before=&date_facets=&o="
    )

    body = response.content.decode()
    attrs = clear_search_link_attrs(body)
    assert attrs is not None
    assert attrs["href"] == "/episodes/"


@pytest.mark.django_db
def test_episode_index_no_results_state_renders_when_search_misses(
    client: Client,
) -> None:
    import_django_chat_sample()

    response = client.get(f"{episode_index_path()}?search=zzzzzznotaword")

    assert response.status_code == 200
    body = response.content.decode()
    assert "No episodes match your filters." in body


@pytest.mark.django_db
def test_episode_index_marks_selected_ordering_in_form(client: Client) -> None:
    import_django_chat_sample()

    response = client.get(f"{episode_index_path()}?o=visible_date")

    body = response.content.decode()
    assert 'value="visible_date" selected' in body
    assert 'value="-visible_date" selected' not in body


@pytest.mark.django_db
def test_episode_index_marks_descending_ordering_in_form(client: Client) -> None:
    import_django_chat_sample()

    response = client.get(f"{episode_index_path()}?o=-visible_date")

    body = response.content.decode()
    assert 'value="-visible_date" selected' in body
    # the ascending option is NOT marked selected when descending is active
    assert 'value="visible_date" selected' not in body


@pytest.mark.django_db
def test_episode_index_ascending_order_renders_oldest_first(client: Client) -> None:
    import_django_chat_sample()

    response = client.get(f"{episode_index_path()}?o=visible_date")

    body = response.content.decode()
    # 2019-02-02 "Preview" is the oldest sample episode; 2026-04-15
    # "Django Tasks - Jake Howard" is the newest. Ascending sort puts
    # Preview first.
    preview_pos = body.find("Preview")
    tasks_pos = body.find("Django Tasks - Jake Howard")
    assert preview_pos > 0 and tasks_pos > 0
    assert preview_pos < tasks_pos, (
        "expected Preview (oldest) to render before Django Tasks (newest) under ?o=visible_date"
    )


@pytest.mark.django_db
def test_episode_index_default_order_renders_newest_first(client: Client) -> None:
    import_django_chat_sample()

    response = client.get(episode_index_path())

    body = response.content.decode()
    preview_pos = body.find("Preview")
    tasks_pos = body.find("Django Tasks - Jake Howard")
    assert preview_pos > 0 and tasks_pos > 0
    assert tasks_pos < preview_pos, (
        "default ordering is descending visible_date — Django Tasks (newest) "
        "must render before Preview (oldest)"
    )


@pytest.mark.django_db
def test_episode_index_filters_by_date_range_after(client: Client) -> None:
    import_django_chat_sample()

    response = client.get(f"{episode_index_path()}?date_after=2026-01-01")

    body = response.content.decode()
    # 2026 episodes should still appear:
    assert "Django Tasks - Jake Howard" in body
    # 2019 sample episodes must be excluded:
    assert "Preview" not in body
    assert "What is Django?" not in body
    assert "How to Learn Django" not in body


@pytest.mark.django_db
def test_episode_index_filters_by_date_range_before(client: Client) -> None:
    import_django_chat_sample()

    response = client.get(f"{episode_index_path()}?date_before=2019-12-31")

    body = response.content.decode()
    # The three 2019 episodes survive:
    assert "What is Django?" in body
    assert "How to Learn Django" in body
    # 2026 episodes are excluded:
    assert "Django Tasks - Jake Howard" not in body


def episode_index_path() -> str:
    return reverse("django_chat_episode_index")


def clear_search_link_attrs(body: str) -> dict[str, str] | None:
    parser = LinkClassParser("filter-search-clear")
    parser.feed(body)
    return parser.attrs


def clear_filters_link_attrs(body: str) -> dict[str, str] | None:
    parser = LinkClassParser("filter-clear-all")
    parser.feed(body)
    return parser.attrs


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


class LinkClassParser(HTMLParser):
    attrs: dict[str, str] | None

    def __init__(self, class_name: str) -> None:
        super().__init__()
        self.class_name = class_name
        self.attrs = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = {key: value or "" for key, value in attrs}
        if tag == "a" and self.class_name in attrs_dict.get("class", "").split():
            self.attrs = attrs_dict
