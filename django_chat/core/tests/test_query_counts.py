from __future__ import annotations

from collections import Counter

import pytest
from cast.models import Episode, Podcast
from django.conf import settings
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from wagtail.models import Page, PageViewRestriction

from django_chat.imports.import_sample import import_django_chat_sample
from django_chat.imports.models import PodcastSourceLink, PodcastSourceMetadata

SOURCE_TABLES = (
    "imports_episodesourcemetadata",
    "imports_podcastsourcemetadata",
    "imports_podcastsourcelink",
)


def _source_table_queries(client: Client, path: str) -> tuple[Counter[str], int]:
    with CaptureQueriesContext(connection) as queries:
        response = client.get(path)
    assert response.status_code == 200
    counts: Counter[str] = Counter()
    for query in queries.captured_queries:
        from_clause = query["sql"].split(" FROM ", 1)[-1]
        for table in SOURCE_TABLES:
            if from_clause.startswith(f'"{table}"'):
                counts[table] += 1
    return counts, len(queries.captured_queries)


@pytest.mark.django_db
def test_episode_index_loads_source_metadata_without_per_row_queries(client: Client) -> None:
    import_django_chat_sample()
    assert Episode.objects.live().count() > 2

    counts, total = _source_table_queries(client, reverse("django_chat_episode_index"))

    # Episode numbers and durations come from a join, the podcast metadata is
    # read once per request, and every link location is served by one prefetch.
    assert counts["imports_episodesourcemetadata"] == 0
    assert counts["imports_podcastsourcemetadata"] == 1
    assert counts["imports_podcastsourcelink"] == 1
    # The whole page, independent of the number of rows: 11 on a cold first
    # request with the sample (23 before; a full page of 20 episodes took 36).
    assert total <= 11


@pytest.mark.django_db
def test_episode_detail_serves_menu_and_social_links_from_one_prefetch(client: Client) -> None:
    import_django_chat_sample()
    episode = Episode.objects.live().order_by("-visible_date").first()
    assert episode is not None

    counts, _total = _source_table_queries(client, episode.url)

    assert counts["imports_podcastsourcemetadata"] == 1
    assert counts["imports_podcastsourcelink"] == 1


@pytest.mark.django_db
def test_visible_links_use_prefetch_and_keep_filter_and_order() -> None:
    import_django_chat_sample()
    metadata = PodcastSourceMetadata.objects.get()
    PodcastSourceLink.objects.create(
        podcast_metadata=metadata,
        source_key="test:menu:hidden",
        source="test",
        location="menu",
        name="Hidden",
        url="https://hidden.test",
        is_visible=False,
    )
    PodcastSourceLink.objects.create(
        podcast_metadata=metadata,
        source_key="test:menu:first",
        source="test",
        location="menu",
        name="AAA First",
        url="https://first.test",
        display_order=0,
    )
    expected = list(
        metadata.source_links.filter(location="menu", is_visible=True).order_by(
            "display_order", "name"
        )
    )

    prefetched = PodcastSourceMetadata.objects.prefetch_related("source_links").get()
    with CaptureQueriesContext(connection) as queries:
        menu = prefetched.visible_menu_links
        social = prefetched.visible_social_links
        distribution = prefetched.visible_distribution_links

    assert len(queries.captured_queries) == 0
    assert menu == expected
    assert "Hidden" not in [link.name for link in menu]
    assert all(link.location == "social" for link in social)
    assert all(link.location == "distribution" for link in distribution)


@pytest.mark.django_db
@pytest.mark.parametrize("restricted", [True, False])
def test_pages_use_the_podcast_under_the_site_root_not_any_page_with_its_slug(
    client: Client, restricted: bool
) -> None:
    import_django_chat_sample()
    public = Podcast.objects.get(slug=settings.DJANGO_CHAT_PODCAST_SLUG)
    episode = Episode.objects.live().child_of(public).order_by("-visible_date").first()
    assert episode is not None
    # Wagtail allows the same slug under another parent. This podcast is not
    # under the site's root page, its metadata sorts first, and (in one case)
    # it is view-restricted, so a lookup by slug alone would hand its links to
    # the public pages.
    other = Podcast(title="Other", slug=settings.DJANGO_CHAT_PODCAST_SLUG)
    Page.get_first_root_node().add_child(instance=other)
    if restricted:
        PageViewRestriction._default_manager.create(
            page=other, restriction_type=PageViewRestriction.LOGIN
        )
    other_metadata = PodcastSourceMetadata.objects.create(
        podcast=other,
        simplecast_podcast_id="other-podcast",
        rss_feed_url="https://other.test/rss",
        simplecast_source_url="https://other.test/api",
        source_title="AAA Other",
    )
    for location in ("menu", "social", "distribution"):
        PodcastSourceLink.objects.create(
            podcast_metadata=other_metadata,
            source_key=f"other:{location}:leak",
            source="other",
            location=location,
            name=f"Other Podcast {location} link",
            url=f"https://other.test/{location}",
        )

    for path in (reverse("django_chat_episode_index"), episode.url, "/episodes/feed/"):
        response = client.get(path)

        assert response.status_code == 200, path
        assert "Other Podcast" not in response.content.decode(), path
        assert response.context["source_metadata"].podcast_id == public.pk, path


@pytest.mark.django_db
def test_episode_index_is_404_without_a_podcast_under_the_site_root(client: Client) -> None:
    import_django_chat_sample()
    public = Podcast.objects.get(slug=settings.DJANGO_CHAT_PODCAST_SLUG)
    PageViewRestriction._default_manager.create(
        page=public, restriction_type=PageViewRestriction.LOGIN
    )

    assert client.get(reverse("django_chat_episode_index")).status_code == 404
