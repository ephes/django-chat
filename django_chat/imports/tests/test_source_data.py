from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from django_chat.imports.source_data import (
    RSS_FEED_URL,
    SIMPLECAST_DISTRIBUTION_CHANNELS_URL,
    SIMPLECAST_PODCAST_ID,
    SIMPLECAST_PODCAST_URL,
    merge_episode_sources,
    parse_rss_feed,
    parse_simplecast_distribution_links,
    parse_simplecast_episode_detail,
    parse_simplecast_episode_page,
    parse_simplecast_podcast,
    parse_simplecast_site,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "django_chat_source"


def test_rss_fixture_parses_podcast_metadata_and_episode_items() -> None:
    feed = parse_rss_feed(_read_text("rss_feed.xml"))

    assert feed.source_url == RSS_FEED_URL
    assert feed.title == "Django Chat"
    assert feed.description == (
        "A biweekly podcast on the Django Web Framework by Will Vincent and Carlton Gibson."
    )
    assert feed.website_url == "https://djangochat.com"
    assert feed.feed_url == RSS_FEED_URL
    assert feed.generator == "https://simplecast.com"
    assert feed.language == "en-us"
    assert feed.author == "William Vincent and Carlton Gibson"
    assert feed.categories == ("Technology", "Education")
    assert feed.explicit is False
    assert "django web framework" in feed.keywords
    assert len(feed.episodes) == 8

    latest = feed.episodes[0]
    assert latest.guid == "2c78bb02-8162-44f0-b22d-a188f5bbdb9e"
    assert latest.guid_is_permalink is False
    assert latest.title == "Django Tasks - Jake Howard"
    assert latest.published_at is not None
    assert latest.published_at.isoformat() == "2026-04-15T08:00:00+00:00"
    assert latest.duration_seconds == 4663
    assert latest.episode_number == 200
    assert latest.episode_type == "full"
    assert latest.enclosure is not None
    assert latest.enclosure.media_type == "audio/mpeg"
    assert latest.enclosure.length == 74615234
    assert latest.enclosure.url.startswith("https://dts.podtrac.com/redirect.mp3/")
    assert "django-tasks" in (latest.description_html or "")
    assert latest.content_html == latest.description_html

    oldest = feed.episodes[-1]
    assert oldest.guid == "697f5867-15e8-414f-b837-4faee703b5cc"
    assert oldest.episode_number == 0
    assert oldest.title == "Preview"


def test_simplecast_podcast_fixture_parses_endpoint_metadata() -> None:
    podcast = parse_simplecast_podcast(_read_json("simplecast_podcast.json"))

    assert podcast.source_url == SIMPLECAST_PODCAST_URL
    assert podcast.id == SIMPLECAST_PODCAST_ID
    assert podcast.title == "Django Chat"
    assert podcast.language == "en-us"
    assert podcast.feed_url == RSS_FEED_URL
    assert podcast.website_url == "https://djangochat.com"
    assert podcast.is_explicit is False
    assert podcast.status == "published"
    assert podcast.episode_count == 203
    assert podcast.author_names == ("William Vincent and Carlton Gibson",)
    assert podcast.site_id == "e7b8d39c-d81e-4eeb-820a-9a2105bad193"
    assert podcast.site_api_url == (
        "https://api.simplecast.com/sites/e7b8d39c-d81e-4eeb-820a-9a2105bad193"
    )
    assert podcast.distribution_channels_url == SIMPLECAST_DISTRIBUTION_CHANNELS_URL
    assert podcast.published_at is not None
    assert podcast.published_at.isoformat() == "2019-02-02T01:56:21+00:00"
    assert podcast.updated_at is not None
    assert podcast.updated_at.isoformat() == "2026-04-15T08:00:16+00:00"


def test_simplecast_episode_list_fixtures_parse_latest_and_oldest_pages() -> None:
    latest_page = parse_simplecast_episode_page(_read_json("simplecast_episode_list_latest.json"))
    oldest_page = parse_simplecast_episode_page(_read_json("simplecast_episode_list_oldest.json"))

    assert latest_page.count == 201
    assert latest_page.page_current == 1
    assert latest_page.page_limit == 5
    assert latest_page.next_url is not None
    assert len(latest_page.episodes) == 5
    assert latest_page.episodes[0].source_kind == "list"
    assert latest_page.episodes[0].id == "af752038-3231-412e-801d-c8cc3cdd90cb"
    assert latest_page.episodes[0].guid == "2c78bb02-8162-44f0-b22d-a188f5bbdb9e"
    assert latest_page.episodes[0].slug == "django-tasks-jake-howard"
    assert latest_page.episodes[0].episode_number == 200
    assert latest_page.episodes[0].season_number == 1
    assert latest_page.episodes[0].duration_seconds == 4663
    assert latest_page.episodes[0].long_description_html is None
    assert latest_page.episodes[0].transcript_html is None

    assert oldest_page.page_current == 67
    assert oldest_page.next_url is None
    assert [episode.episode_number for episode in oldest_page.episodes] == [2, 1, 0]
    assert oldest_page.episodes[-1].slug == "preview"


def test_simplecast_episode_detail_fixtures_preserve_transcript_html() -> None:
    latest = parse_simplecast_episode_detail(
        _read_json("simplecast_episode_detail_200_django-tasks-jake-howard.json")
    )
    older = parse_simplecast_episode_detail(
        _read_json("simplecast_episode_detail_2_how-to-learn-django.json")
    )

    assert latest.source_kind == "detail"
    assert latest.id == "af752038-3231-412e-801d-c8cc3cdd90cb"
    assert latest.guid == "2c78bb02-8162-44f0-b22d-a188f5bbdb9e"
    assert latest.slug == "django-tasks-jake-howard"
    assert latest.episode_number == 200
    assert latest.enclosure_url is not None
    assert latest.enclosure_url.startswith("https://dts.podtrac.com/redirect.mp3/")
    assert latest.audio_file_size == 74615234
    assert latest.long_description_html is not None
    assert "Django-Mantle" in latest.long_description_html
    assert latest.transcript_html is not None
    assert latest.transcript_html.startswith("<p>")
    assert "Jake Howard" in latest.transcript_html

    assert older.id == "85357cab-bd4c-449a-9530-c262a458728d"
    assert older.episode_number == 2
    assert older.transcript_html is not None
    assert len(older.transcript_html) > 50_000


def test_all_captured_detail_fixtures_parse() -> None:
    expected = {
        "simplecast_episode_detail_0_preview.json": (
            "4f9f2269-7780-430e-b2bc-bd91cde19b58",
            "preview",
            0,
        ),
        "simplecast_episode_detail_1_what-is-django.json": (
            "2ee6175b-05b4-41de-8fb9-f84bf96eaacb",
            "what-is-django",
            1,
        ),
        "simplecast_episode_detail_2_how-to-learn-django.json": (
            "85357cab-bd4c-449a-9530-c262a458728d",
            "how-to-learn-django",
            2,
        ),
        "simplecast_episode_detail_200_django-tasks-jake-howard.json": (
            "af752038-3231-412e-801d-c8cc3cdd90cb",
            "django-tasks-jake-howard",
            200,
        ),
    }

    for filename, (episode_id, slug, number) in expected.items():
        episode = parse_simplecast_episode_detail(_read_json(filename))

        assert episode.id == episode_id
        assert episode.slug == slug
        assert episode.episode_number == number


def test_simplecast_site_fixture_parses_menu_and_social_links() -> None:
    site = parse_simplecast_site(_read_json("simplecast_site.json"))

    assert site.id == "e7b8d39c-d81e-4eeb-820a-9a2105bad193"
    assert site.podcast_id == SIMPLECAST_PODCAST_ID
    assert site.external_website == "https://djangochat.com"
    assert site.cname_url == "djangochat.com"
    assert site.privacy_policy_link is None
    assert site.privacy_policy_text is None
    assert site.legacy_hosts is None

    assert [link.name for link in site.menu_links] == ["YouTube", "Sponsor Us", "Fosstodon"]
    assert [link.order for link in site.menu_links] == [100, 200, 300]
    assert site.menu_links[0].url == "https://www.youtube.com/@djangochat"
    assert site.menu_links[1].url.startswith("https://docs.google.com/document/")
    assert site.social_links[0].name == "Fosstodon"
    assert site.social_links[0].url == "https://fosstodon.org/@djangochat"


def test_simplecast_distribution_fixture_parses_distribution_links() -> None:
    links = parse_simplecast_distribution_links(_read_json("simplecast_distribution_channels.json"))

    assert len(links) == 7
    by_name = {link.name: link for link in links}
    assert (
        by_name["Apple Podcasts"].url
        == "https://itunes.apple.com/us/podcast/django-chat/id1451536459"
    )
    assert by_name["Spotify"].url == (
        "https://open.spotify.com/show/4JTUPoJhFKOjbzNbGmIq5l?si=16457669e4134436"
    )
    assert by_name["Google Podcasts"].channel_id == "00512816-1bf2-4828-9f69-5f6fcb3f68f6"
    assert all(link.location == "distribution" for link in links)


def test_endpoint_assisted_merge_matches_by_guid_and_preserves_source_fields() -> None:
    feed = parse_rss_feed(_read_text("rss_feed.xml"))
    detail = parse_simplecast_episode_detail(
        _read_json("simplecast_episode_detail_200_django-tasks-jake-howard.json")
    )

    merged = merge_episode_sources((feed.episodes[0],), (detail,))

    assert len(merged) == 1
    episode = merged[0]
    assert episode.matching_key == "guid:2c78bb02-8162-44f0-b22d-a188f5bbdb9e"
    assert episode.title == "Django Tasks - Jake Howard"
    assert episode.rss_guid == "2c78bb02-8162-44f0-b22d-a188f5bbdb9e"
    assert episode.simplecast_episode_id == "af752038-3231-412e-801d-c8cc3cdd90cb"
    assert episode.slug == "django-tasks-jake-howard"
    assert episode.episode_number == 200
    assert episode.rss_enclosure_url is not None
    assert episode.rss_enclosure_url.endswith("?aid=rss_feed&feed=WpQaX_cs")
    assert episode.simplecast_enclosure_url is not None
    assert not episode.simplecast_enclosure_url.endswith("?aid=rss_feed&feed=WpQaX_cs")
    assert episode.rss is feed.episodes[0]
    assert episode.simplecast is detail


def test_endpoint_assisted_merge_falls_back_to_episode_number_when_guid_is_missing() -> None:
    feed = parse_rss_feed(_read_text("rss_feed.xml"))
    payload = _read_json("simplecast_episode_detail_200_django-tasks-jake-howard.json")
    payload.pop("guid")
    detail = parse_simplecast_episode_detail(payload)

    merged = merge_episode_sources((feed.episodes[0],), (detail,))

    assert len(merged) == 1
    episode = merged[0]
    assert episode.matching_key == "guid:2c78bb02-8162-44f0-b22d-a188f5bbdb9e"
    assert episode.rss_guid == "2c78bb02-8162-44f0-b22d-a188f5bbdb9e"
    assert episode.simplecast_episode_id == "af752038-3231-412e-801d-c8cc3cdd90cb"
    assert episode.slug == "django-tasks-jake-howard"
    assert episode.episode_number == 200


def test_rss_only_fallback_keeps_identifiers_without_simplecast_data() -> None:
    feed = parse_rss_feed(_read_text("rss_feed.xml"))

    merged = merge_episode_sources((feed.episodes[0],))

    assert len(merged) == 1
    episode = merged[0]
    assert episode.matching_key == "guid:2c78bb02-8162-44f0-b22d-a188f5bbdb9e"
    assert episode.rss_guid == "2c78bb02-8162-44f0-b22d-a188f5bbdb9e"
    assert episode.simplecast_episode_id is None
    assert episode.slug is None
    assert episode.episode_number == 200
    assert episode.rss_enclosure_url is not None
    assert episode.simplecast_enclosure_url is None
    assert episode.rss is feed.episodes[0]
    assert episode.simplecast is None


def test_simplecast_parser_allows_missing_optional_endpoint_fields() -> None:
    payload = _read_json("simplecast_episode_detail_200_django-tasks-jake-howard.json")
    for key in (
        "audio_file_size",
        "audio_file_url",
        "description",
        "duration",
        "enclosure_url",
        "episode_url",
        "guid",
        "is_explicit",
        "is_hidden",
        "long_description",
        "number",
        "published_at",
        "season",
        "slug",
        "status",
        "transcription",
        "updated_at",
    ):
        payload.pop(key, None)

    episode = parse_simplecast_episode_detail(payload)

    assert episode.id == "af752038-3231-412e-801d-c8cc3cdd90cb"
    assert episode.title == "Django Tasks - Jake Howard"
    assert episode.guid is None
    assert episode.slug is None
    assert episode.episode_number is None
    assert episode.enclosure_url is None
    assert episode.long_description_html is None
    assert episode.transcript_html is None


def test_simplecast_parser_treats_malformed_optional_values_as_missing() -> None:
    payload = _read_json("simplecast_episode_detail_200_django-tasks-jake-howard.json")
    payload["audio_file_size"] = True
    payload["duration"] = True
    payload["number"] = False
    payload["published_at"] = "unknown"
    payload["updated_at"] = "not-a-date"
    payload.pop("href")

    episode = parse_simplecast_episode_detail(payload)

    assert episode.source_url == (
        "https://api.simplecast.com/episodes/af752038-3231-412e-801d-c8cc3cdd90cb"
    )
    assert episode.audio_file_size is None
    assert episode.duration_seconds is None
    assert episode.episode_number is None
    assert episode.published_at is None
    assert episode.updated_at is None


def test_link_parsers_strip_public_urls_and_ignore_boolean_order_values() -> None:
    site_payload = _read_json("simplecast_site.json")
    site_payload["menu_links"]["collection"][0]["url"] = " https://www.youtube.com/@djangochat "
    site_payload["menu_links"]["collection"][0]["order"] = True
    distribution_payload = _read_json("simplecast_distribution_channels.json")
    distribution_payload["collection"][0]["url"] = (
        " https://itunes.apple.com/us/podcast/django-chat/id1451536459 "
    )

    site = parse_simplecast_site(site_payload)
    links = parse_simplecast_distribution_links(distribution_payload)

    youtube = next(link for link in site.menu_links if link.name == "YouTube")
    assert youtube.url == "https://www.youtube.com/@djangochat"
    assert youtube.order is None
    assert links[0].url == "https://itunes.apple.com/us/podcast/django-chat/id1451536459"


def test_fixture_manifest_documents_public_sources_and_capture_time() -> None:
    manifest = _read_json("manifest.json")
    expected_files = {
        "rss_feed.xml",
        "simplecast_distribution_channels.json",
        "simplecast_episode_detail_0_preview.json",
        "simplecast_episode_detail_1_what-is-django.json",
        "simplecast_episode_detail_2_how-to-learn-django.json",
        "simplecast_episode_detail_200_django-tasks-jake-howard.json",
        "simplecast_episode_list_latest.json",
        "simplecast_episode_list_oldest.json",
        "simplecast_podcast.json",
        "simplecast_site.json",
    }

    assert manifest["captured_at"].startswith("2026-04-21T")
    assert set(manifest["files"]) == expected_files
    assert manifest["files"]["rss_feed.xml"] == RSS_FEED_URL
    assert manifest["files"]["simplecast_podcast.json"] == SIMPLECAST_PODCAST_URL
    assert manifest["files"]["simplecast_distribution_channels.json"] == (
        SIMPLECAST_DISTRIBUTION_CHANNELS_URL
    )
    assert "network access" in manifest["note"]


def _read_text(filename: str) -> str:
    return (FIXTURE_DIR / filename).read_text(encoding="utf-8")


def _read_json(filename: str) -> dict[str, Any]:
    payload = json.loads(_read_text(filename))
    assert isinstance(payload, dict)
    return payload
