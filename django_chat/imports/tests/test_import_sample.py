from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any, cast

import pytest
from cast.models import Audio, Episode, Podcast
from django.apps import apps
from django.core.management import call_command
from django.test import override_settings
from wagtail.models import Site

from django_chat.imports.import_sample import (
    DownloadedAudio,
    import_django_chat_sample,
    import_django_chat_source_data,
    load_sample_source_data,
)
from django_chat.imports.models import (
    EpisodeAudioImportMetadata,
    EpisodeSourceMetadata,
    PodcastSourceLink,
    PodcastSourceMetadata,
)
from django_chat.imports.source_data import (
    RSS_FEED_URL,
    SIMPLECAST_PODCAST_ID,
    SIMPLECAST_PODCAST_URL,
)

EPISODE_ONE_KEYWORDS = "technology, web, programming, python, django"


def test_sample_source_matching_keys_are_stable() -> None:
    first_load = load_sample_source_data()
    second_load = load_sample_source_data()

    first_keys = tuple(episode.matching_key for episode in first_load.episodes)
    second_keys = tuple(episode.matching_key for episode in second_load.episodes)

    assert first_keys == second_keys
    assert len(set(first_keys)) == len(first_keys)
    assert "guid:2c78bb02-8162-44f0-b22d-a188f5bbdb9e" in first_keys


@pytest.mark.django_db
def test_sample_import_creates_podcast_episode_pages_and_source_metadata() -> None:
    result = import_django_chat_sample()

    assert result.podcast_created is True
    assert result.episodes_created == 8
    assert len(result.episodes) == 8
    assert len(result.episode_metadata) == 8
    assert Podcast.objects.count() == 1
    assert Episode.objects.count() == 8
    assert PodcastSourceMetadata.objects.count() == 1
    assert PodcastSourceLink.objects.count() == 11
    assert EpisodeSourceMetadata.objects.count() == 8
    assert EpisodeAudioImportMetadata.objects.count() == 0

    podcast = Podcast.objects.get()
    assert podcast.title == "Django Chat"
    assert podcast.slug == "episodes"
    assert podcast.author == "William Vincent and Carlton Gibson"
    assert podcast.email == "will@wsvincent.com"
    assert podcast.comments_enabled is False
    assert podcast.template_base_dir == "django_chat"

    podcast_metadata = PodcastSourceMetadata.objects.get()
    assert podcast_metadata.podcast == podcast
    assert podcast_metadata.simplecast_podcast_id == SIMPLECAST_PODCAST_ID
    assert podcast_metadata.rss_feed_url == RSS_FEED_URL
    assert podcast_metadata.simplecast_source_url == SIMPLECAST_PODCAST_URL
    assert podcast_metadata.website_url == "https://djangochat.com"
    assert podcast_metadata.source_is_explicit is False
    assert [link.name for link in podcast_metadata.visible_menu_links] == [
        "YouTube",
        "Sponsor Us",
        "Fosstodon",
    ]
    assert [link.name for link in podcast_metadata.visible_social_links] == ["Fosstodon"]
    assert "Apple Podcasts" in {link.name for link in podcast_metadata.visible_distribution_links}

    latest_metadata = EpisodeSourceMetadata.objects.get(episode_number=200)
    assert latest_metadata.episode.title == "Django Tasks - Jake Howard"
    assert latest_metadata.rss_guid == "2c78bb02-8162-44f0-b22d-a188f5bbdb9e"
    assert latest_metadata.simplecast_episode_id == "af752038-3231-412e-801d-c8cc3cdd90cb"
    assert latest_metadata.simplecast_slug == "django-tasks-jake-howard"
    assert latest_metadata.matching_key == "guid:2c78bb02-8162-44f0-b22d-a188f5bbdb9e"
    assert latest_metadata.rss_source_url == RSS_FEED_URL
    assert latest_metadata.simplecast_source_url.startswith("https://api.simplecast.com/episodes/")
    assert latest_metadata.original_rss_enclosure_url.endswith("?aid=rss_feed&feed=WpQaX_cs")
    assert latest_metadata.simplecast_enclosure_url.startswith(
        "https://dts.podtrac.com/redirect.mp3/"
    )
    assert not latest_metadata.simplecast_enclosure_url.endswith("?aid=rss_feed&feed=WpQaX_cs")
    assert latest_metadata.simplecast_audio_file_url.startswith("https://cdn.simplecast.com/")
    assert latest_metadata.duration_seconds == 4663
    assert latest_metadata.audio_file_size == 74615234
    assert latest_metadata.rss_is_explicit is False
    assert latest_metadata.simplecast_is_explicit is False
    assert "Django-Mantle" in latest_metadata.simplecast_long_description_html
    assert latest_metadata.simplecast_transcript_html.startswith("<p>")
    assert "Jake Howard" in latest_metadata.simplecast_transcript_html
    assert latest_metadata.episode.podcast_audio is None
    assert latest_metadata.episode.comments_enabled is False
    assert latest_metadata.episode.owner.username == "django-chat-importer"
    first_metadata = EpisodeSourceMetadata.objects.get(episode_number=1)
    assert first_metadata.episode.keywords == EPISODE_ONE_KEYWORDS
    assert cast(Any, first_metadata.episode).tags.count() == 0
    assert Audio.objects.count() == 0
    assert _transcript_count() == 0
    assert result.audio_created == 0
    assert result.audio_copied == 0
    assert result.audio_metadata == ()


@pytest.mark.django_db
def test_sample_import_structures_detail_show_note_sections() -> None:
    import_django_chat_sample()

    latest_metadata = EpisodeSourceMetadata.objects.get(episode_number=200)
    latest_detail = _body_children(latest_metadata.episode, "detail")
    structured_types = [child["type"] for child in latest_detail]

    assert structured_types == [
        "show_note_link_list",
        "show_note_link_list",
        "show_note_link_list",
        "show_note_link_list",
        "show_note_sponsor",
    ]
    assert [
        child["value"]["kind"] for child in latest_detail if child["type"] == "show_note_link_list"
    ] == ["links", "projects", "books", "youtube"]
    links = latest_detail[0]["value"]
    link_items = _list_values(links["items"])
    assert links["heading"] == "Links"
    assert link_items[0]["title"] == "django-tasks"
    assert link_items[0]["url"] == "https://github.com/RealOrangeOne/django-tasks"
    assert _list_values(link_items[0]["extra_links"]) == [
        {"title": "Jake's GitHub", "url": "https://github.com/realorangeone"}
    ]
    books = latest_detail[2]["value"]
    assert _list_values(books["items"])[0]["title"] == "The Passage by Justin Cronin"
    sponsor = latest_detail[4]["value"]
    assert sponsor["heading"] == "Sponsor"
    assert sponsor["sponsor_name"] == "Buttondown"
    assert sponsor["sponsor_url"] == "https://buttondown.com/django"
    assert "This episode was brought to you by" in sponsor["copy"]
    assert "<p>🔗 Links</p>" in latest_metadata.simplecast_long_description_html
    assert "<p>🤝 Sponsor</p>" in latest_metadata.simplecast_long_description_html

    first_metadata = EpisodeSourceMetadata.objects.get(episode_number=1)
    first_detail = _body_children(first_metadata.episode, "detail")
    assert first_detail[-1]["type"] == "show_note_link_list"
    assert first_detail[-1]["value"]["kind"] == "shameless_plugs"
    assert first_detail[-1]["value"]["heading"] == "Shameless Plugs"
    assert "<h4>SHAMELESS PLUGS</h4>" in first_metadata.simplecast_long_description_html

    second_metadata = EpisodeSourceMetadata.objects.get(episode_number=2)
    second_detail = _body_children(second_metadata.episode, "detail")
    assert [child["value"]["kind"] for child in second_detail[-2:]] == [
        "groups",
        "shameless_plugs",
    ]
    assert "<h4>Groups</h4>" in second_metadata.simplecast_long_description_html


@pytest.mark.django_db
def test_show_note_structuring_preserves_existing_h3_and_ordinary_paragraphs() -> None:
    sample = load_sample_source_data()
    episode_source = sample.episodes[0]
    assert episode_source.simplecast is not None
    source_detail_html = (
        "<p>Intro copy stays an ordinary paragraph.</p>"
        "<h3>Sponsor</h3>"
        '<p>This episode was brought to you by <a href="https://example.com" '
        'rel="noopener noreferrer"><strong>Example</strong></a>.</p>'
        '<p>A normal paragraph with <a href="https://example.com/link" '
        'rel="nofollow">a link</a> stays a paragraph.</p>'
    )
    customized_episode = replace(
        episode_source,
        simplecast=replace(
            episode_source.simplecast,
            long_description_html=source_detail_html,
        ),
    )
    source_data = replace(sample, episodes=(customized_episode,))

    result = import_django_chat_source_data(source_data)

    metadata = result.episode_metadata[0]
    detail_blocks = _body_children(metadata.episode, "detail")
    overview = _body_block_html(metadata.episode, "overview")
    assert detail_blocks[0] == {
        "type": "paragraph",
        "value": "<p>Intro copy stays an ordinary paragraph.</p>",
        "id": detail_blocks[0]["id"],
    }
    assert detail_blocks[1]["type"] == "show_note_sponsor"
    assert detail_blocks[1]["value"]["heading"] == "Sponsor"
    assert detail_blocks[1]["value"]["sponsor_name"] == "Example"
    assert (
        '<p>This episode was brought to you by <a href="https://example.com" '
        'rel="noopener noreferrer"><strong>Example</strong></a>.</p>'
    ) in detail_blocks[1]["value"]["copy"]
    assert (
        '<p>A normal paragraph with <a href="https://example.com/link" '
        'rel="nofollow">a link</a> stays a paragraph.</p>'
    ) in detail_blocks[1]["value"]["copy"]
    assert metadata.simplecast_long_description_html == source_detail_html
    assert overview == episode_source.simplecast.description


@pytest.mark.django_db
def test_sample_import_is_idempotent_on_second_run() -> None:
    first_result = import_django_chat_sample()
    podcast_ids = set(Podcast.objects.values_list("id", flat=True))
    episode_ids = set(Episode.objects.values_list("id", flat=True))
    podcast_metadata_ids = set(PodcastSourceMetadata.objects.values_list("id", flat=True))
    episode_metadata_ids = set(EpisodeSourceMetadata.objects.values_list("id", flat=True))
    source_link_ids = set(PodcastSourceLink.objects.values_list("id", flat=True))

    second_result = import_django_chat_sample()

    assert first_result.podcast_created is True
    assert first_result.episodes_created == 8
    assert second_result.podcast_created is False
    assert second_result.episodes_created == 0
    assert set(Podcast.objects.values_list("id", flat=True)) == podcast_ids
    assert set(Episode.objects.values_list("id", flat=True)) == episode_ids
    assert set(PodcastSourceMetadata.objects.values_list("id", flat=True)) == podcast_metadata_ids
    assert set(EpisodeSourceMetadata.objects.values_list("id", flat=True)) == episode_metadata_ids
    assert set(PodcastSourceLink.objects.values_list("id", flat=True)) == source_link_ids
    assert Podcast.objects.count() == 1
    assert Episode.objects.count() == 8
    assert PodcastSourceMetadata.objects.count() == 1
    assert PodcastSourceLink.objects.count() == 11
    assert EpisodeSourceMetadata.objects.count() == 8
    assert EpisodeAudioImportMetadata.objects.count() == 0
    assert Audio.objects.count() == 0
    assert _transcript_count() == 0


@pytest.mark.django_db
def test_sample_import_backfills_episode_keywords_on_reimport() -> None:
    import_django_chat_sample()
    first_metadata = EpisodeSourceMetadata.objects.get(episode_number=1)
    first_episode = first_metadata.episode
    episode_ids = set(Episode.objects.values_list("id", flat=True))

    assert first_episode.keywords == EPISODE_ONE_KEYWORDS
    first_episode.keywords = ""
    first_episode.save(update_fields=["keywords"])

    result = import_django_chat_sample()

    assert result.episodes_created == 0
    assert set(Episode.objects.values_list("id", flat=True)) == episode_ids
    first_episode.refresh_from_db()
    assert first_episode.keywords == EPISODE_ONE_KEYWORDS
    assert cast(Any, first_episode).tags.count() == 0


@pytest.mark.django_db
def test_import_sample_management_command_uses_local_fixtures() -> None:
    call_command("import_django_chat_sample", verbosity=0)

    assert PodcastSourceMetadata.objects.get().simplecast_podcast_id == SIMPLECAST_PODCAST_ID
    assert EpisodeSourceMetadata.objects.count() == 8
    assert EpisodeAudioImportMetadata.objects.count() == 0
    assert Audio.objects.count() == 0
    assert _transcript_count() == 0


@pytest.mark.django_db
def test_sample_import_rejects_episode_slug_collision_without_source_metadata() -> None:
    source_data = load_sample_source_data()
    parent_page = Site.objects.select_related("root_page").get(is_default_site=True).root_page
    podcast = Podcast(title="Django Chat", slug="episodes", description="")
    parent_page.add_child(instance=podcast)
    colliding_episode = Episode(
        title="Different Episode",
        slug=source_data.episodes[0].slug or "",
        body=[("overview", [("paragraph", "Different episode")])],
    )
    podcast.add_child(instance=colliding_episode)

    with pytest.raises(RuntimeError, match="Episode slug collision"):
        import_django_chat_sample()


@pytest.mark.django_db
def test_sample_import_can_copy_audio_with_fake_downloader(tmp_path: Path) -> None:
    downloader = FakeAudioDownloader()

    with override_settings(MEDIA_ROOT=tmp_path):
        result = import_django_chat_sample(copy_audio=True, audio_downloader=downloader)

    assert result.audio_created == 8
    assert result.audio_copied == 8
    assert len(result.audio_metadata) == 8
    assert len(downloader.urls) == 8
    assert Podcast.objects.count() == 1
    assert Episode.objects.count() == 8
    assert EpisodeSourceMetadata.objects.count() == 8
    assert EpisodeAudioImportMetadata.objects.count() == 8
    assert Audio.objects.count() == 8
    assert _transcript_count() == 0
    assert not downloader.urls[0].endswith("?aid=rss_feed&feed=WpQaX_cs")

    latest_metadata = EpisodeSourceMetadata.objects.get(episode_number=200)
    audio_metadata = latest_metadata.audio_import_metadata
    assert audio_metadata.source_url == latest_metadata.simplecast_audio_file_url
    assert audio_metadata.source_url_kind == "simplecast_audio_file_url"
    assert audio_metadata.source_content_type == "audio/mpeg"
    assert audio_metadata.source_byte_size == 74615234
    assert audio_metadata.copied_byte_size == len(_fake_audio_content(audio_metadata.source_url))
    assert audio_metadata.storage_name.startswith(
        "cast_audio/django-chat-sample/django-tasks-jake-howard-"
    )
    assert (tmp_path / audio_metadata.storage_name).exists()

    latest_episode = cast(Episode, latest_metadata.episode)
    latest_episode.refresh_from_db()
    latest_audio = cast(Audio, audio_metadata.audio)
    latest_audio_fields = cast(Any, latest_audio)
    assert cast(Any, latest_episode).podcast_audio == latest_audio
    assert latest_audio_fields.title == "Django Tasks - Jake Howard"
    assert latest_audio_fields.subtitle == "Episode 200"
    assert latest_audio_fields.duration.total_seconds() == 4663
    assert latest_audio_fields.user.username == "django-chat-importer"
    assert latest_audio_fields.data["django_chat_source"] == {
        "matching_key": latest_metadata.matching_key,
        "source_url": audio_metadata.source_url,
        "source_url_kind": "simplecast_audio_file_url",
    }
    assert latest_audio_fields.data["size"]["mp3"] == len(
        _fake_audio_content(audio_metadata.source_url)
    )


@pytest.mark.django_db
def test_sample_audio_copy_is_idempotent_on_second_run(tmp_path: Path) -> None:
    downloader = FakeAudioDownloader()

    with override_settings(MEDIA_ROOT=tmp_path):
        first_result = import_django_chat_sample(copy_audio=True, audio_downloader=downloader)
        audio_ids = set(Audio.objects.values_list("id", flat=True))
        audio_modified = dict(Audio.objects.values_list("id", "modified"))
        audio_metadata_ids = set(EpisodeAudioImportMetadata.objects.values_list("id", flat=True))
        episode_ids = set(Episode.objects.values_list("id", flat=True))
        storage_names = set(
            EpisodeAudioImportMetadata.objects.values_list("storage_name", flat=True)
        )

        second_result = import_django_chat_sample(
            copy_audio=True,
            audio_downloader=FailingAudioDownloader(),
        )

    assert first_result.audio_created == 8
    assert first_result.audio_copied == 8
    assert second_result.audio_created == 0
    assert second_result.audio_copied == 0
    assert len(downloader.urls) == 8
    assert set(Audio.objects.values_list("id", flat=True)) == audio_ids
    assert dict(Audio.objects.values_list("id", "modified")) == audio_modified
    assert (
        set(EpisodeAudioImportMetadata.objects.values_list("id", flat=True)) == audio_metadata_ids
    )
    assert set(Episode.objects.values_list("id", flat=True)) == episode_ids
    assert (
        set(EpisodeAudioImportMetadata.objects.values_list("storage_name", flat=True))
        == storage_names
    )
    assert Podcast.objects.count() == 1
    assert Episode.objects.count() == 8
    assert EpisodeSourceMetadata.objects.count() == 8
    assert EpisodeAudioImportMetadata.objects.count() == 8
    assert Audio.objects.count() == 8
    assert all(
        cast(Any, episode).podcast_audio_id is not None
        for episode in Episode.objects.only("podcast_audio").all()
    )
    assert _transcript_count() == 0


@pytest.mark.django_db
def test_sample_audio_copy_redownloads_missing_stored_file(tmp_path: Path) -> None:
    first_downloader = FakeAudioDownloader()

    with override_settings(MEDIA_ROOT=tmp_path):
        import_django_chat_sample(copy_audio=True, audio_downloader=first_downloader)
        audio_metadata = EpisodeAudioImportMetadata.objects.order_by("id").first()
        assert audio_metadata is not None
        stored_file = tmp_path / audio_metadata.storage_name
        stored_file.unlink()

        second_downloader = FakeAudioDownloader()
        result = import_django_chat_sample(copy_audio=True, audio_downloader=second_downloader)

    assert result.audio_created == 0
    assert result.audio_copied == 1
    assert second_downloader.urls == [audio_metadata.source_url]
    assert stored_file.exists()


@pytest.mark.django_db
def test_import_sample_management_command_can_copy_audio(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    downloader = FakeAudioDownloader()
    monkeypatch.setattr(
        "django_chat.imports.import_sample.default_download_audio",
        downloader,
    )

    with override_settings(MEDIA_ROOT=tmp_path):
        call_command("import_django_chat_sample", "--copy-audio", verbosity=0)

    assert len(downloader.urls) == 8
    assert Audio.objects.count() == 8
    assert EpisodeAudioImportMetadata.objects.count() == 8
    assert Episode.objects.filter(podcast_audio__isnull=False).count() == 8
    assert _transcript_count() == 0


@pytest.mark.django_db
def test_sample_import_attaches_show_cover_image_when_downloader_provided(
    tmp_path: Path,
) -> None:
    image_downloader = FakeImageDownloader()

    with override_settings(MEDIA_ROOT=tmp_path):
        result = import_django_chat_sample(cover_image_downloader=image_downloader)

    podcast = Podcast.objects.get(pk=result.podcast.pk)
    assert podcast.cover_image is not None
    assert "Django Chat" in podcast.cover_image.title
    assert len(image_downloader.urls) == 1


@pytest.mark.django_db
def test_sample_import_does_not_attach_cover_when_downloader_omitted(
    tmp_path: Path,
) -> None:
    with override_settings(MEDIA_ROOT=tmp_path):
        result = import_django_chat_sample()

    podcast = Podcast.objects.get(pk=result.podcast.pk)
    assert podcast.cover_image is None


@pytest.mark.django_db
def test_sample_import_skips_cover_download_when_already_set(tmp_path: Path) -> None:
    image_downloader = FakeImageDownloader()

    with override_settings(MEDIA_ROOT=tmp_path):
        first = import_django_chat_sample(cover_image_downloader=image_downloader)
        # Re-import — cover_image is already set, so no further download:
        second = import_django_chat_sample(cover_image_downloader=image_downloader)

    assert first.podcast.pk == second.podcast.pk
    assert len(image_downloader.urls) == 1


def _transcript_count() -> int:
    transcript = cast(Any, apps.get_model("cast", "Transcript"))
    return transcript.objects.count()


def _body_block_html(episode: Any, block_type: str) -> str:
    return "".join(
        child["value"]
        for child in _body_children(episode, block_type)
        if child["type"] == "paragraph"
    )


def _body_children(episode: Any, block_type: str) -> list[dict[str, Any]]:
    body_data = episode.body.get_prep_value()
    for block in body_data:
        if block["type"] == block_type:
            return block["value"]
    msg = f"Episode body does not contain a {block_type!r} block."
    raise AssertionError(msg)


def _list_values(value: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [item["value"] if item.get("type") == "item" else item for item in value]


class FakeAudioDownloader:
    def __init__(self) -> None:
        self.urls: list[str] = []

    def __call__(self, source_url: str) -> DownloadedAudio:
        self.urls.append(source_url)
        content = _fake_audio_content(source_url)
        return DownloadedAudio(
            content=content,
            content_type="audio/mpeg",
            content_length=len(content),
            filename="sample.mp3",
        )


class FailingAudioDownloader:
    def __call__(self, source_url: str) -> DownloadedAudio:
        msg = f"Unexpected audio download during idempotent import: {source_url}"
        raise AssertionError(msg)


def _fake_audio_content(source_url: str) -> bytes:
    return f"fake audio bytes for {source_url}".encode()


# Minimal valid 1x1 PNG. Wagtail's Image.save() runs Pillow on the bytes
# to read dimensions, so the file must parse — a string of bytes won't.
def _make_fake_png() -> bytes:
    import io

    from PIL import Image as PILImage

    buf = io.BytesIO()
    PILImage.new("RGB", (1, 1), color=(0, 0, 0)).save(buf, format="PNG")
    return buf.getvalue()


_FAKE_PNG = _make_fake_png()


class FakeImageDownloader:
    def __init__(self, *, content: bytes = _FAKE_PNG) -> None:
        self.urls: list[str] = []
        self._content = content

    def __call__(self, source_url: str) -> bytes:
        self.urls.append(source_url)
        return self._content
