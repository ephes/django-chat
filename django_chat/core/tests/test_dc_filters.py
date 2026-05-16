from __future__ import annotations

from types import SimpleNamespace

import pytest

from django_chat.core.templatetags.dc_filters import (
    duration_minutes,
    platform_icon,
    split_amazon_audible,
    youtube_first,
)


@pytest.mark.parametrize(
    "seconds,expected",
    [
        (4663, "78 MIN"),
        (60, "1 MIN"),
        (29, "0 MIN"),
        (None, ""),
        (0, ""),
    ],
)
def test_duration_minutes_formats_or_returns_empty(seconds, expected):
    assert duration_minutes(seconds) == expected


@pytest.mark.parametrize(
    "name,expected_suffix",
    [
        ("Apple Podcasts", "/apple-podcasts.svg"),
        ("apple podcasts", "/apple-podcasts.svg"),
        ("  Spotify  ", "/spotify.svg"),
        ("Amazon Music and Audible", "/amazon-music.svg"),
        ("Amazon Music", "/amazon-music.svg"),
        ("Audible", "/audible.svg"),
        ("Pocketcast", "/pocket-casts.svg"),
    ],
)
def test_platform_icon_returns_static_url_for_known_names(name, expected_suffix):
    assert platform_icon(name).endswith(expected_suffix)


@pytest.mark.parametrize("value", [None, "", "unknown platform", 123, object()])
def test_platform_icon_returns_empty_for_unknown_or_non_string(value):
    assert platform_icon(value) == ""


def _link(name: str) -> SimpleNamespace:
    return SimpleNamespace(name=name, url=f"https://example.test/{name.lower()}")


def test_youtube_first_moves_youtube_to_front():
    links = [_link("Apple Podcasts"), _link("Overcast"), _link("YouTube"), _link("Spotify")]
    ordered = youtube_first(links)
    assert [link.name for link in ordered] == ["YouTube", "Apple Podcasts", "Overcast", "Spotify"]


def test_youtube_first_is_noop_when_youtube_already_first():
    links = [_link("YouTube"), _link("Apple Podcasts")]
    assert youtube_first(links) == links


def test_youtube_first_is_noop_when_youtube_absent():
    links = [_link("Apple Podcasts"), _link("Spotify")]
    assert [link.name for link in youtube_first(links)] == ["Apple Podcasts", "Spotify"]


def test_split_amazon_audible_replaces_combined_entry_with_two_links():
    combined = _link("Amazon Music and Audible")
    spotify = _link("Spotify")
    result = split_amazon_audible([combined, spotify])
    names = [link.name for link in result]
    assert names == ["Amazon Music", "Audible", "Spotify"]
    amazon, audible = result[0], result[1]
    assert amazon.url == combined.url
    assert audible.url.startswith("https://www.audible.de/podcast/Django-Chat/")


def test_split_amazon_audible_is_noop_when_combined_entry_absent():
    spotify = _link("Spotify")
    result = split_amazon_audible([spotify])
    assert result == [spotify]
