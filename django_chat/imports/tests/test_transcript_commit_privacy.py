"""Commit timing and diagnostics through the public transcript importer."""

from email.message import Message
from io import StringIO

import pytest
from django.apps import apps
from django.core.management import call_command
from django.db import transaction

from django_chat.imports import staging_transcripts as staging
from django_chat.imports.tests.test_staging_transcripts import _podlove_segment
from django_chat.imports.tests.test_transcript_validation import episode as episode
from django_chat.imports.tests.test_transcript_validation import fetch, files
from django_chat.imports.url_safety import UnsafeURLError, validate_outbound_url


@pytest.mark.django_db
def test_outer_rollback_preserves_previous_database_names_and_bytes(episode, tmp_path):
    payload = {"transcripts": [_podlove_segment()]}
    assert staging.import_staging_transcript_for_episode(
        episode, text_fetcher=fetch(payload)
    ).imported
    model = apps.get_model("cast", "Transcript")
    previous = model.objects.get(audio=episode.podcast_audio)
    names = (previous.podlove.name, previous.vtt.name, previous.dote.name)
    before = files(tmp_path)
    with pytest.raises(RuntimeError, match="outer rollback"), transaction.atomic():
        assert staging.import_staging_transcript_for_episode(
            episode, text_fetcher=fetch(payload)
        ).imported
        # Old bytes must survive until commit.
        for name in names:
            assert (tmp_path / name).exists()
        raise RuntimeError("outer rollback")
    previous.refresh_from_db()
    assert (previous.podlove.name, previous.vtt.name, previous.dote.name) == names
    for name, content in before.items():
        assert (tmp_path / name).read_bytes() == content


@pytest.mark.django_db
def test_serialized_replacements_retire_only_previous_generations(
    episode, tmp_path, monkeypatch, django_capture_on_commit_callbacks
):
    payload = {"transcripts": [_podlove_segment()]}
    model = apps.get_model("cast", "Transcript")
    assert staging.import_staging_transcript_for_episode(
        episode, text_fetcher=fetch(payload)
    ).imported
    previous = model.objects.get(audio=episode.podcast_audio)
    old_names = [previous.podlove.name, previous.vtt.name, previous.dote.name]
    deleted = []
    storage = previous.podlove.storage
    original = storage.delete

    def delete(name):
        deleted.append(name)
        original(name)

    monkeypatch.setattr(storage, "delete", delete)
    with django_capture_on_commit_callbacks(execute=True), transaction.atomic():
        for _ in range(2):
            assert staging.import_staging_transcript_for_episode(
                episode, text_fetcher=fetch(payload)
            ).imported
            previous.refresh_from_db()
        winner = [previous.podlove.name, previous.vtt.name, previous.dote.name]
        assert deleted == []
    assert len(deleted) == 6
    assert len(set(deleted)) == 6
    assert set(old_names) <= set(deleted)
    assert not set(winner) & set(deleted)
    assert all(storage.exists(name) for name in winner)


SECRETS = ("invented-user", "invented-password", "invented-query", "invented-fragment")
URL = "http://invented-user:invented-password@127.0.0.1/private?token=invented-query#invented-fragment"


def test_url_policy_errors_do_not_contain_credentials():
    with pytest.raises(UnsafeURLError) as error:
        validate_outbound_url(URL)
    assert "non-public" in str(error.value)
    assert all(secret not in str(error.value) for secret in SECRETS)
    assert len(str(error.value)) < 200


@pytest.mark.django_db
@pytest.mark.parametrize("error", [OSError, ValueError, UnsafeURLError])
def test_import_and_command_diagnostics_are_safe_to_retain(episode, monkeypatch, error):
    def fail(*args):
        raise error(f"failed fetch of {URL}")

    result = staging.import_staging_transcript_for_episode(episode, text_fetcher=fail)
    assert not result.imported and result.reason
    assert all(secret not in result.reason for secret in SECRETS)
    monkeypatch.setattr(staging, "default_fetch_text", fail)
    stdout, stderr = StringIO(), StringIO()
    call_command(
        "import_django_chat_staging_transcripts", slug=[episode.slug], stdout=stdout, stderr=stderr
    )
    output = stdout.getvalue() + stderr.getvalue()
    assert output
    assert all(secret not in output for secret in SECRETS)


@pytest.mark.django_db
def test_publication_locks_parent_and_transcript_before_writes(episode, monkeypatch):
    from django.db.models import QuerySet

    events = []
    original_lock = QuerySet.select_for_update
    original_replace = staging._replace_file

    def lock(queryset, *args, **kwargs):
        events.append(("lock", queryset.model._meta.label_lower))
        return original_lock(queryset, *args, **kwargs)

    def replace(*args, **kwargs):
        events.append(("write", "artifact"))
        return original_replace(*args, **kwargs)

    monkeypatch.setattr(QuerySet, "select_for_update", lock)
    monkeypatch.setattr(staging, "_replace_file", replace)
    assert staging.import_staging_transcript_for_episode(
        episode, text_fetcher=fetch({"transcripts": [_podlove_segment()]})
    ).imported
    first_write = events.index(("write", "artifact"))
    assert ("lock", "cast.audio") in events[:first_write]
    assert ("lock", "cast.transcript") in events[:first_write]


def test_fetch_open_failure_never_echoes_transport_url(monkeypatch):
    from django_chat.imports import url_safety

    class Opener:
        def open(self, *args, **kwargs):
            raise OSError(f"synthetic failed redirect {URL}")

    monkeypatch.setattr(url_safety, "validate_outbound_url", lambda url: url)
    monkeypatch.setattr(url_safety, "build_opener", lambda *args: Opener())
    with pytest.raises(OSError) as error:
        url_safety.safe_urlopen(URL, timeout=1)
    assert "HTTP fetch failed" in str(error.value)
    assert all(secret not in str(error.value) for secret in SECRETS)


@pytest.mark.django_db
def test_retirement_callback_uses_the_write_alias(episode, monkeypatch):
    from functools import partial

    aliases = []
    original = transaction.on_commit

    def register(callback, using=None, robust=False):
        if isinstance(callback, partial) and callback.func is staging._delete_replacement_files:
            aliases.append(using)
        return original(callback, using=using, robust=robust)

    monkeypatch.setattr(transaction, "on_commit", register)
    assert staging.import_staging_transcript_for_episode(
        episode, text_fetcher=fetch({"transcripts": [_podlove_segment()]})
    ).imported
    assert aliases == [episode._state.db]


def test_http_failure_closes_error_response_and_keeps_safe_status(monkeypatch):
    import io
    from urllib.error import HTTPError

    from django_chat.imports import url_safety

    body = io.BytesIO(b"synthetic error body")

    class Opener:
        def open(self, *args, **kwargs):
            raise HTTPError(URL, 403, f"refused {URL}", Message(), body)

    monkeypatch.setattr(url_safety, "validate_outbound_url", lambda url: url)
    monkeypatch.setattr(url_safety, "build_opener", lambda *args: Opener())
    with pytest.raises(OSError) as error:
        url_safety.safe_urlopen(URL, timeout=1)
    assert isinstance(error.value, HTTPError) and error.value.code == 403
    assert body.closed
    assert all(secret not in str(error.value) for secret in SECRETS)


@pytest.mark.django_db
def test_expected_missing_transcript_keeps_safe_reason(episode):
    from django_chat.imports.tests.test_staging_transcripts import _custom_player_html

    result = staging.import_staging_transcript_for_episode(
        episode,
        text_fetcher=lambda *args: _custom_player_html(
            audio_id=1, post_id=4, with_transcript=False
        ),
    )
    assert not result.imported
    assert result.reason == "staging episode page exposes no transcript for this episode"


@pytest.mark.django_db
def test_http_status_survives_real_wrapper_in_staging_and_feed_diagnostics(episode, monkeypatch):
    from urllib.error import HTTPError

    from django_chat.imports import live_feed_parity, url_safety

    class Opener:
        def open(self, *args, **kwargs):
            raise HTTPError(URL, 404, f"missing {URL}", Message(), None)

    monkeypatch.setattr(url_safety, "validate_outbound_url", lambda url: url)
    monkeypatch.setattr(url_safety, "build_opener", lambda *args: Opener())
    result = staging.import_staging_transcript_for_episode(episode)
    assert result.reason == "staging fetch failed (HTTP 404)"
    with pytest.raises(live_feed_parity.FeedFetchError, match="returned HTTP 404") as error:
        live_feed_parity.fetch_feed_bytes(URL)
    assert all(secret not in str(error.value) for secret in SECRETS)
    stdout, stderr = StringIO(), StringIO()
    from django.core.management.base import CommandError

    with pytest.raises(CommandError):
        call_command(
            "compare_django_chat_live_feed",
            source_url=URL,
            candidate_url=URL,
            stdout=stdout,
            stderr=stderr,
        )
    assert "404" in stdout.getvalue()
    assert all(secret not in stdout.getvalue() + stderr.getvalue() for secret in SECRETS)


@pytest.mark.django_db
def test_exception_after_atomic_exit_does_not_delete_published_files(episode, monkeypatch):
    from contextlib import contextmanager

    original_atomic = transaction.atomic
    depth = [0]

    @contextmanager
    def atomic_with_exit_failure(*args, **kwargs):
        depth[0] += 1
        outermost = depth[0] == 1
        try:
            with original_atomic(*args, **kwargs):
                yield
        finally:
            depth[0] -= 1
        if outermost:
            raise RuntimeError("synthetic post-commit callback failure")

    monkeypatch.setattr(transaction, "atomic", atomic_with_exit_failure)
    with pytest.raises(RuntimeError, match="post-commit callback failure"):
        staging.import_staging_transcript_for_episode(
            episode, text_fetcher=fetch({"transcripts": [_podlove_segment()]})
        )
    transcript = apps.get_model("cast", "Transcript").objects.get(audio=episode.podcast_audio)
    for field in (transcript.podlove, transcript.vtt, transcript.dote):
        assert field.storage.exists(field.name)
