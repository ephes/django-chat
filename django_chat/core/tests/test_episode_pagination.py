from __future__ import annotations

from unittest.mock import patch

import pytest
from django.test import Client

from django_chat.imports.import_sample import import_django_chat_sample


@pytest.mark.django_db
def test_pagination_markup_hidden_for_eight_episode_fixture(client: Client) -> None:
    import_django_chat_sample()

    response = client.get("/episodes/")

    body = response.content.decode()
    assert response.context["is_paginated"] is False
    assert 'class="pagination-nav"' not in body


@pytest.mark.django_db
def test_pagination_markup_visible_when_page_size_is_small(client: Client) -> None:
    import_django_chat_sample()

    with patch("django_chat.core.views.EPISODES_PER_PAGE", 3):
        response = client.get("/episodes/?search=django")

    body = response.content.decode()
    assert response.context["is_paginated"] is True
    assert 'class="pagination-nav"' in body
    # parameters context preserves the active filter on Older/Newer links
    assert "search=django" in body


@pytest.mark.django_db
def test_pagination_parameters_context_value_strips_page_only(client: Client) -> None:
    import_django_chat_sample()

    with patch("django_chat.core.views.EPISODES_PER_PAGE", 3):
        response = client.get("/episodes/?search=django&page=2")

    parameters = response.context["parameters"]
    assert "search=django" in parameters
    assert "page=" not in parameters
