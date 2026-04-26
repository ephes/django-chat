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
