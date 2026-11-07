"""Transcript schema and owned-file rollback regressions, all synthetic."""

import json

import pytest
from django.apps import apps
from django.core.files.base import ContentFile

from django_chat.imports import staging_transcripts as staging
from django_chat.imports.import_sample import import_django_chat_sample
from django_chat.imports.tests.test_staging_transcripts import (
    FakeAudioDownloader,
    _custom_player_html,
    _podlove_segment,
)


@pytest.fixture
def episode(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    result = import_django_chat_sample(copy_audio=True, audio_downloader=FakeAudioDownloader())
    episode = next(e for e in result.episodes if e.slug == "django-tasks-jake-howard")
    episode.refresh_from_db()
    return episode


def fetch(payload):
    return lambda url, timeout: (
        json.dumps(payload) if "/api/" in url else _custom_player_html(audio_id=1, post_id=4)
    )


def files(root):
    return {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()}


INVALID = [
    [],
    None,
    "text",
    {"transcripts": "text"},
    {"transcripts": [None]},
    {"transcripts": [_podlove_segment() | {"text": 42}]},
    *(
        {"transcripts": [_podlove_segment() | patch]}
        for patch in [
            {"start": "nonsense"},
            {"start": "NaN"},
            {"end": "Infinity"},
            {"start": -1},
            {"end": "-5"},
            {"start": "00:00:03.000"},
            {"start_ms": True},
            {"end_ms": 1999},
            {"end": "00:99:00.000"},
            {"speaker": []},
            {"text": "x" * 16385},
        ]
    ),
]


@pytest.mark.django_db
@pytest.mark.parametrize("payload", INVALID)
def test_bad_transcript_payload_preserves_existing_files(episode, tmp_path, payload):
    first = staging.import_staging_transcript_for_episode(
        episode, text_fetcher=fetch({"transcripts": [_podlove_segment()]})
    )
    assert first.imported
    before = files(tmp_path)
    transcript_model = apps.get_model("cast", "Transcript")
    previous = transcript_model.objects.get(audio=episode.podcast_audio)
    names = (previous.podlove.name, previous.vtt.name, previous.dote.name)
    result = staging.import_staging_transcript_for_episode(episode, text_fetcher=fetch(payload))
    assert not result.imported
    assert result.reason
    previous.refresh_from_db()
    assert (previous.podlove.name, previous.vtt.name, previous.dote.name) == names
    assert files(tmp_path) == before


@pytest.mark.django_db
@pytest.mark.parametrize("failure", [2, 3, 4])
@pytest.mark.parametrize("existing", [False, True])
def test_failed_artifact_publication_removes_new_owned_files(
    episode, tmp_path, monkeypatch, failure, existing
):
    payload = {"transcripts": [_podlove_segment()]}
    if existing:
        assert staging.import_staging_transcript_for_episode(
            episode, text_fetcher=fetch(payload)
        ).imported
    before = files(tmp_path)
    original = staging._replace_file
    calls = []

    def replacement(*args):
        calls.append(len(calls) + 1)
        if len(calls) == failure:
            raise RuntimeError("synthetic artifact failure")
        return original(*args)

    monkeypatch.setattr(staging, "_replace_file", replacement)
    if failure == 4:
        transcript_model = apps.get_model("cast", "Transcript")

        def fail_save(*args, **kwargs):
            # get_or_create inserts a blank transcript before any artifact exists.
            if kwargs.get("update_fields"):
                calls.append(4)
                raise RuntimeError("synthetic artifact failure")
            return original_save(*args, **kwargs)

        original_save = transcript_model.save
        monkeypatch.setattr(transcript_model, "save", fail_save)
    with pytest.raises(RuntimeError, match="synthetic artifact failure"):
        staging.import_staging_transcript_for_episode(episode, text_fetcher=fetch(payload))
    assert calls[-1] == failure
    assert files(tmp_path) == before


def test_first_file_returns_owned_handle():
    from django_chat.imports.tests.test_staging_transcripts import FakeField, FakeStorage

    field = FakeField(FakeStorage(), "")
    owned = staging._replace_file(field, "new.json", ContentFile("new"))
    assert owned is not None
    assert not owned.old_name
    staging._delete_replacement_files([owned], use_new=True)
    assert field.storage.events[-1] == ("delete", owned.new_name)


@pytest.mark.django_db
def test_valid_fractional_timing_is_preserved_exactly(episode):
    segment = _podlove_segment() | {
        "start": "00:00:01.123",
        "start_ms": 1123,
        "end": "00:00:01.124",
        "end_ms": 1124,
    }
    result = staging.import_staging_transcript_for_episode(
        episode, text_fetcher=fetch({"transcripts": [segment]})
    )
    assert result.imported
    transcript = apps.get_model("cast", "Transcript").objects.get(audio=episode.podcast_audio)
    assert transcript.podlove_data["transcripts"] == [segment]
    assert transcript.dote_data["lines"][0]["startTime"] == "00:00:01,123"
    assert "00:00:01.123 --> 00:00:01.124" in transcript.vtt.read().decode()


@pytest.mark.django_db
@pytest.mark.parametrize("blank", [None, "", "   "])
def test_diarization_gaps_and_null_milliseconds_are_compatible(episode, blank):
    segment = _podlove_segment()
    payload = {
        "transcripts": [segment | {"text": blank}, segment | {"start_ms": None, "end_ms": None}]
    }
    result = staging.import_staging_transcript_for_episode(episode, text_fetcher=fetch(payload))
    assert result.imported and result.segment_count == 1
    transcript = apps.get_model("cast", "Transcript").objects.get(audio=episode.podcast_audio)
    assert transcript.podlove_data["transcripts"] == [segment]


@pytest.mark.django_db
def test_untrusted_text_cannot_inject_webvtt_cues(episode):
    segment = _podlove_segment() | {"text": "a\n\n00:00:09.000 --> 00:00:10.000\nfake <b> &"}
    result = staging.import_staging_transcript_for_episode(
        episode, text_fetcher=fetch({"transcripts": [segment]})
    )
    assert result.imported
    transcript = apps.get_model("cast", "Transcript").objects.get(audio=episode.podcast_audio)
    content = transcript.vtt.read().decode()
    assert content.count("-->") == 1
    assert "\n\n00:00:09" not in content
    assert "&lt;b&gt; &amp;" in content
    assert transcript.podlove_data["transcripts"][0]["text"] == segment["text"]
