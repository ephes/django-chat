"""View-restricted episodes must never leak through Django Chat's custom views.

Wagtail enforces page view restrictions only in ``Page.serve()``. The episode
index, the embed player and the latest-entries feed render episodes without
going through ``serve()``, so they must filter with ``.live().public()`` and
the feed must refuse restricted podcast roots like django-cast's own feeds.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from xml.etree import ElementTree

import pytest
from cast.models import Episode, Podcast
from django.conf import settings as django_settings
from django.contrib.auth.models import Group
from django.core.cache import cache
from django.test import Client, RequestFactory, TestCase
from django.urls import reverse
from wagtail.models import Page, PageViewRestriction

from django_chat.core import feeds as chat_feeds
from django_chat.imports.import_sample import DownloadedAudio, import_django_chat_sample


@pytest.fixture(autouse=True)
def _clear_feed_cache() -> Iterator[None]:
    # The feed route sits behind cache_page; keep rendered feeds from leaking
    # between tests (and between the before/after renders inside one test).
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def sample_podcast(settings: Any, tmp_path: Any) -> Podcast:
    # Copy (fake) audio so every episode qualifies for the feed, which only
    # lists episodes with podcast audio.
    settings.MEDIA_ROOT = tmp_path
    import_django_chat_sample(copy_audio=True, audio_downloader=FakeAudioDownloader())
    return Podcast.objects.get(slug=django_settings.DJANGO_CHAT_PODCAST_SLUG)


RESTRICTION_KINDS = ["login", "password", "groups"]
restrictions: Any = PageViewRestriction._default_manager


def restrict(page: Page, kind: str) -> PageViewRestriction:
    # The cache invalidation runs on commit; run those callbacks as a real
    # commit would, since each test is wrapped in a transaction.
    with TestCase.captureOnCommitCallbacks(execute=True):
        return _create_restriction(page, kind)


def unrestrict(restriction: PageViewRestriction) -> None:
    with TestCase.captureOnCommitCallbacks(execute=True):
        restriction.delete()


def _create_restriction(page: Page, kind: str) -> PageViewRestriction:
    if kind == "login":
        return restrictions.create(page=page, restriction_type=PageViewRestriction.LOGIN)
    if kind == "password":
        return restrictions.create(
            page=page, restriction_type=PageViewRestriction.PASSWORD, password="sesame"
        )
    restriction = restrictions.create(page=page, restriction_type=PageViewRestriction.GROUPS)
    restriction.groups.add(Group.objects.create(name="Insiders"))
    return restriction


def first_episode(podcast: Podcast) -> Episode:
    episode = Episode.objects.live().child_of(podcast).order_by("-visible_date").first()
    assert episode is not None
    return episode


def feed_path() -> str:
    return reverse("django_chat_latest_entries_feed")


def feed_item_links(content: bytes) -> list[str]:
    root = ElementTree.fromstring(content)
    return [link.text or "" for link in root.iter("item") for link in link.findall("link")]


def index_slugs(response: Any) -> list[str]:
    return [post.slug for post in response.context["posts"]]


@pytest.mark.django_db
@pytest.mark.parametrize("kind", RESTRICTION_KINDS)
def test_feed_omits_view_restricted_episode(
    client: Client, sample_podcast: Podcast, kind: str
) -> None:
    episode = first_episode(sample_podcast)
    public_links = feed_item_links(client.get(feed_path()).content)
    assert any(link.endswith(f"/{episode.slug}/") for link in public_links)

    # No cache.clear() here: the warm cached feed must not outlive the
    # restriction.
    restrict(episode, kind)
    response = client.get(feed_path())

    assert response.status_code == 200
    links = feed_item_links(response.content)
    assert not any(link.endswith(f"/{episode.slug}/") for link in links)
    assert len(links) == len(public_links) - 1
    assert str(episode.title).encode() not in response.content


@pytest.mark.django_db
def test_feed_shows_episode_again_after_restriction_is_removed(
    client: Client, sample_podcast: Podcast
) -> None:
    episode = first_episode(sample_podcast)
    restriction = restrict(episode, "login")
    assert not any(
        link.endswith(f"/{episode.slug}/")
        for link in feed_item_links(client.get(feed_path()).content)
    )

    unrestrict(restriction)

    assert any(
        link.endswith(f"/{episode.slug}/")
        for link in feed_item_links(client.get(feed_path()).content)
    )


@pytest.mark.django_db
def test_view_restriction_change_clears_cached_django_cast_podcast_feed(
    client: Client, sample_podcast: Podcast
) -> None:
    # The same invalidation protects django-cast's own cached podcast feed.
    episode = first_episode(sample_podcast)
    path = reverse("cast:podcast_feed_rss", args=[sample_podcast.slug, "mp3"])
    assert str(episode.title).encode() in client.get(path).content

    restrict(episode, "password")

    assert str(episode.title).encode() not in client.get(path).content


@pytest.mark.django_db
def test_restriction_clears_cache_only_after_commit(
    client: Client, sample_podcast: Podcast
) -> None:
    # A clear before commit would let another worker refill the cache from
    # the pre-restriction state.
    episode = first_episode(sample_podcast)
    client.get(feed_path())
    generation = chat_feeds.feed_cache_generation()

    with TestCase.captureOnCommitCallbacks(execute=False) as callbacks:
        _create_restriction(episode, "login")
        assert chat_feeds.feed_cache_generation() == generation

    assert callbacks
    for callback in callbacks:
        callback()
    assert chat_feeds.feed_cache_generation() != generation


@pytest.mark.django_db
def test_feed_render_in_flight_during_restriction_is_not_served_later(
    client: Client, sample_podcast: Podcast, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The first request renders the public feed, then the restriction commits
    # before cache_page stores that (now stale) response.
    episode = first_episode(sample_podcast)
    original_call = chat_feeds.DjangoChatLatestEntriesFeed.__call__
    restricted: list[PageViewRestriction] = []

    def render_then_restrict(self: Any, request: Any, *args: Any, **kwargs: Any) -> Any:
        response = original_call(self, request, *args, **kwargs)
        if not restricted:
            restricted.append(restrict(episode, "login"))
        return response

    monkeypatch.setattr(chat_feeds.DjangoChatLatestEntriesFeed, "__call__", render_then_restrict)

    stale = client.get(feed_path())
    assert any(link.endswith(f"/{episode.slug}/") for link in feed_item_links(stale.content))

    fresh = client.get(feed_path())

    assert restricted
    assert not any(link.endswith(f"/{episode.slug}/") for link in feed_item_links(fresh.content))


@pytest.mark.django_db
@pytest.mark.parametrize("kind", RESTRICTION_KINDS)
def test_feed_returns_404_for_restricted_podcast(
    client: Client, sample_podcast: Podcast, kind: str
) -> None:
    episode = first_episode(sample_podcast)
    restrict(sample_podcast, kind)

    response = client.get(feed_path())

    assert response.status_code == 404
    assert str(episode.title).encode() not in response.content


@pytest.mark.django_db
def test_feed_restricted_podcast_is_refused_even_when_cached(
    client: Client, sample_podcast: Podcast
) -> None:
    # The restriction check runs before the shared response cache.
    assert client.get(feed_path()).status_code == 200

    restrict(sample_podcast, "login")

    assert client.get(feed_path()).status_code == 404


@pytest.mark.django_db
def test_feed_output_is_unchanged_for_public_episodes(
    client: Client, sample_podcast: Podcast
) -> None:
    # Byte-equality: the .public() filter and the per-request renderer change
    # nothing for an all-public catalog. The reference render uses the feed
    # class directly, bypassing the URL wrappers and the response cache.
    expected = chat_feeds.DjangoChatLatestEntriesFeed()(
        RequestFactory().get(feed_path()), slug=django_settings.DJANGO_CHAT_PODCAST_SLUG
    ).content

    response = client.get(feed_path())

    assert response.status_code == 200
    assert response.content == expected
    assert (
        len(feed_item_links(response.content))
        == Episode.objects.live().child_of(sample_podcast).count()
    )


@pytest.mark.django_db
def test_feed_creates_a_renderer_per_request(
    client: Client, sample_podcast: Podcast, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Keep the instances alive so a reused id() cannot mask a shared renderer.
    instances: list[Any] = []
    original_init = chat_feeds.DjangoChatLatestEntriesFeed.__init__

    def tracking_init(self: Any, *args: Any, **kwargs: Any) -> None:
        instances.append(self)
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(chat_feeds.DjangoChatLatestEntriesFeed, "__init__", tracking_init)

    for _ in range(2):
        cache.clear()
        assert client.get(feed_path()).status_code == 200

    assert len(instances) == 2
    assert instances[0] is not instances[1]


@pytest.mark.django_db
@pytest.mark.parametrize("kind", RESTRICTION_KINDS)
def test_index_omits_view_restricted_episode(
    client: Client, sample_podcast: Podcast, kind: str
) -> None:
    episode = first_episode(sample_podcast)
    before = client.get(reverse("django_chat_episode_index"))
    assert episode.slug in index_slugs(before)

    restrict(episode, kind)
    response = client.get(reverse("django_chat_episode_index"))

    assert response.status_code == 200
    assert episode.slug not in index_slugs(response)
    assert response.context["paginator"].count == before.context["paginator"].count - 1
    assert episode.title not in response.content.decode()


@pytest.mark.django_db
@pytest.mark.parametrize("kind", RESTRICTION_KINDS)
def test_index_returns_404_for_restricted_podcast(
    client: Client, sample_podcast: Podcast, kind: str
) -> None:
    episode = first_episode(sample_podcast)
    restrict(sample_podcast, kind)

    response = client.get(reverse("django_chat_episode_index"))

    assert response.status_code == 404
    assert episode.title not in response.content.decode()


@pytest.mark.django_db
@pytest.mark.parametrize("kind", RESTRICTION_KINDS)
def test_embed_returns_404_for_view_restricted_episode(
    client: Client, sample_podcast: Podcast, kind: str
) -> None:
    episode = first_episode(sample_podcast)
    assert client.get(embed_path(episode)).status_code == 200

    restrict(episode, kind)

    assert client.get(embed_path(episode)).status_code == 404


@pytest.mark.django_db
@pytest.mark.parametrize("kind", RESTRICTION_KINDS)
def test_embed_returns_404_under_restricted_podcast(
    client: Client, sample_podcast: Podcast, kind: str
) -> None:
    episode = first_episode(sample_podcast)
    restrict(sample_podcast, kind)

    assert client.get(embed_path(episode)).status_code == 404


@pytest.mark.django_db
def test_public_episodes_still_render_in_index_and_embed(
    client: Client, sample_podcast: Podcast
) -> None:
    episodes = list(Episode.objects.live().child_of(sample_podcast))

    response = client.get(reverse("django_chat_episode_index"))

    assert response.context["paginator"].count == len(episodes)
    for episode in episodes:
        assert client.get(embed_path(episode)).status_code == 200


def embed_path(episode: Episode) -> str:
    return reverse("django_chat_episode_embed", kwargs={"episode_slug": episode.slug})


class FakeAudioDownloader:
    def __call__(self, source_url: str) -> DownloadedAudio:
        return DownloadedAudio(
            content=f"fake audio bytes for {source_url}".encode(),
            content_type="audio/mpeg",
            content_length=123,
            filename="sample.mp3",
        )
