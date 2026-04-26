from __future__ import annotations

import pytest
from django.test import Client

from django_chat.imports.import_sample import import_django_chat_sample


@pytest.mark.django_db
def test_episode_index_filters_by_search_query(client: Client) -> None:
    import_django_chat_sample()

    response = client.get("/episodes/?search=tasks")

    assert response.status_code == 200
    body = response.content.decode()
    assert "Django Tasks - Jake Howard" in body
    assert "How to Learn Django" not in body


@pytest.mark.django_db
def test_episode_index_unfiltered_lists_all_sample_episodes(client: Client) -> None:
    import_django_chat_sample()

    response = client.get("/episodes/")

    assert response.status_code == 200
    body = response.content.decode()
    assert "Django Tasks - Jake Howard" in body
    assert "How to Learn Django" in body


@pytest.mark.django_db
def test_episode_index_exposes_filterset_form_fields(client: Client) -> None:
    import_django_chat_sample()

    response = client.get("/episodes/")

    body = response.content.decode()
    assert 'name="search"' in body
    assert 'name="date_after"' in body
    assert 'name="date_before"' in body
    assert 'name="date_facets"' in body
    assert 'name="o"' in body


@pytest.mark.django_db
def test_episode_index_no_results_state_renders_when_search_misses(
    client: Client,
) -> None:
    import_django_chat_sample()

    response = client.get("/episodes/?search=zzzzzznotaword")

    assert response.status_code == 200
    body = response.content.decode()
    assert "No episodes match your filters." in body


@pytest.mark.django_db
def test_episode_index_marks_selected_ordering_in_form(client: Client) -> None:
    import_django_chat_sample()

    response = client.get("/episodes/?o=visible_date")

    body = response.content.decode()
    assert 'value="visible_date" selected' in body
    assert 'value="-visible_date" selected' not in body


@pytest.mark.django_db
def test_episode_index_marks_descending_ordering_in_form(client: Client) -> None:
    import_django_chat_sample()

    response = client.get("/episodes/?o=-visible_date")

    body = response.content.decode()
    assert 'value="-visible_date" selected' in body
    # the ascending option is NOT marked selected when descending is active
    assert 'value="visible_date" selected' not in body


@pytest.mark.django_db
def test_episode_index_ascending_order_renders_oldest_first(client: Client) -> None:
    import_django_chat_sample()

    response = client.get("/episodes/?o=visible_date")

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

    response = client.get("/episodes/")

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

    response = client.get("/episodes/?date_after=2026-01-01")

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

    response = client.get("/episodes/?date_before=2019-12-31")

    body = response.content.decode()
    # The three 2019 episodes survive:
    assert "What is Django?" in body
    assert "How to Learn Django" in body
    # 2026 episodes are excluded:
    assert "Django Tasks - Jake Howard" not in body
