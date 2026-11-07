"""Synthetic races and storage failures through both public audio-copy paths."""

from typing import Any, cast

import pytest
from cast.models import Audio

from django_chat.imports import import_sample as sample
from django_chat.imports.models import EpisodeAudioImportMetadata, EpisodeSourceMetadata


@pytest.fixture
def audio_state(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    result = sample.import_django_chat_sample()
    metadata = result.episode_metadata[0]
    copied = sample.copy_django_chat_sample_audio((metadata,), audio_downloader=download)[0]
    return metadata, copied, tmp_path


def download(url):
    return sample.DownloadedAudio(b"original audio", content_length=14, filename="synthetic.mp3")


def copy(metadata, streaming, callback):
    if not streaming:
        return sample.copy_django_chat_sample_audio((metadata,), audio_downloader=callback)

    def stream(url, destination):
        payload = callback(url)
        destination.write_bytes(payload.content)
        return sample.DownloadedAudioFile(
            destination,
            len(payload.content),
            content_length=payload.content_length,
            filename="synthetic.mp3",
        )

    return sample.copy_django_chat_catalog_audio((metadata,), audio_downloader=stream)


@pytest.mark.django_db
@pytest.mark.parametrize("streaming", [False, True])
@pytest.mark.parametrize(
    "change",
    ["simplecast_audio_file_url", "simplecast_episode_id", "audio_file_size", "duration_seconds"],
)
def test_source_generation_change_rejects_publication(audio_state, streaming, change):
    metadata, previous, root = audio_state
    EpisodeSourceMetadata.objects.filter(pk=metadata.pk).update(
        simplecast_audio_file_url="https://media.example.test/new.mp3"
    )
    metadata.refresh_from_db()
    old_name = previous.audio.mp3.name
    old_bytes = (root / old_name).read_bytes()
    injected = []

    def racing_download(url):
        new_value = (
            "https://media.example.test/newer.mp3"
            if change.endswith("url")
            else "new-identity"
            if change.endswith("id")
            else 999
        )
        EpisodeSourceMetadata.objects.filter(pk=metadata.pk).update(**{change: new_value})
        injected.append(change)
        return download(url)

    with pytest.raises(ValueError, match="changed.*rerun"):
        copy(metadata, streaming, racing_download)
    assert injected == [change]
    previous.audio.refresh_from_db()
    previous.audio_metadata.refresh_from_db()
    assert previous.audio.mp3.name == old_name
    assert previous.audio_metadata.storage_name == old_name
    assert (root / old_name).read_bytes() == old_bytes


@pytest.mark.django_db
@pytest.mark.parametrize("streaming", [False, True])
@pytest.mark.parametrize("failure", ["audio-save", "import-metadata", "attachment"])
def test_publication_failure_compensates_only_owned_files(
    audio_state, streaming, failure, monkeypatch
):
    metadata, previous, root = audio_state
    EpisodeSourceMetadata.objects.filter(pk=metadata.pk).update(
        simplecast_audio_file_url="https://media.example.test/new.mp3"
    )
    metadata.refresh_from_db()
    old_name = previous.audio.mp3.name
    before = {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()}
    injected = []

    def fail(*args, **kwargs):
        injected.append(failure)
        raise RuntimeError("synthetic publication failure")

    if failure == "audio-save":
        monkeypatch.setattr(Audio, "save", fail)
    elif failure == "import-metadata":
        monkeypatch.setattr(EpisodeAudioImportMetadata.objects, "update_or_create", fail)
    else:
        monkeypatch.setattr(sample, "_attach_episode_audio", fail)
    with pytest.raises(RuntimeError, match="synthetic publication failure"):
        copy(metadata, streaming, download)
    assert injected == [failure]
    previous.audio.refresh_from_db()
    previous.audio_metadata.refresh_from_db()
    assert previous.audio.mp3.name == old_name
    assert previous.audio_metadata.storage_name == old_name
    assert {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()} == before


@pytest.mark.django_db
@pytest.mark.parametrize("streaming", [False, True])
def test_unchanged_source_publishes_and_keeps_new_file(audio_state, streaming):
    metadata, previous, root = audio_state
    EpisodeSourceMetadata.objects.filter(pk=metadata.pk).update(
        simplecast_audio_file_url="https://media.example.test/new.mp3"
    )
    metadata.refresh_from_db()
    result = copy(metadata, streaming, download)[0]
    assert result.file_copied
    assert (root / result.audio.mp3.name).read_bytes() == b"original audio"
    assert (root / previous.audio.mp3.name).read_bytes() == b"original audio"


@pytest.mark.django_db
def test_long_slug_keeps_full_unique_generation_in_storage_name(audio_state):
    from unittest.mock import patch
    from uuid import UUID

    metadata, previous, root = audio_state
    metadata.simplecast_slug = "a" * 48
    payload = download("synthetic")
    identity = UUID("12345678-1234-5678-1234-567812345678")
    with patch.object(sample, "uuid4", return_value=identity):
        for prefix in (sample.SAMPLE_AUDIO_STORAGE_PREFIX, sample.CATALOG_AUDIO_STORAGE_PREFIX):
            name = sample._destination_audio_filename(metadata, payload, storage_prefix=prefix)
            field = cast(Any, Audio)._meta.get_field("mp3")
            full_name = field.generate_filename(previous.audio, name)
            assert len(full_name) <= field.max_length
            assert identity.hex in full_name
