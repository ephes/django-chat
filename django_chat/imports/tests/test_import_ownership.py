from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pytest
from cast.models import Episode, Podcast
from django.db import connection, connections
from django.test import override_settings

from django_chat.imports import import_sample as importer
from django_chat.imports.models import PodcastSourceMetadata
from django_chat.imports.tests.test_catalog_boundaries import artwork


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_cover_network_work_precedes_owner_reservation(tmp_path: Path) -> None:
    def download(_: str) -> bytes:
        assert not connection.in_atomic_block
        return artwork()

    with override_settings(MEDIA_ROOT=tmp_path):
        importer.import_django_chat_sample(cover_image_downloader=download)


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_postgres_first_import_has_one_owner(monkeypatch: Any) -> None:
    if connection.vendor != "postgresql":
        pytest.skip("requires two committed PostgreSQL connections; see import docs")
    source = importer.load_sample_source_data()
    first_entered = threading.Event()
    second_started = threading.Event()
    second_entered = threading.Event()
    release_first = threading.Event()
    original = importer._get_or_create_podcast_page
    local = threading.local()

    def observe(*args: Any, **kwargs: Any) -> Any:
        if getattr(local, "worker", "retry") == "first":
            first_entered.set()
            assert release_first.wait(10)
        else:
            second_entered.set()
        return original(*args, **kwargs)

    def run(worker: str) -> Any:
        local.worker = worker
        connections.close_all()
        try:
            if worker == "second":
                second_started.set()
            return importer.import_django_chat_source_data(source)
        finally:
            connections.close_all()

    monkeypatch.setattr(importer, "_get_or_create_podcast_page", observe)
    with ThreadPoolExecutor(max_workers=2) as workers:
        first = workers.submit(run, "first")
        assert first_entered.wait(10)
        second = workers.submit(run, "second")
        try:
            assert second_started.wait(10)
            assert not second_entered.wait(1), (
                "second importer entered absence checks without ownership"
            )
        finally:
            release_first.set()
        first_result = first.result(timeout=20)
        second_result = second.result(timeout=20)
    assert first_result.podcast.pk == second_result.podcast.pk
    assert first_result.podcast_created and not second_result.podcast_created
    assert Podcast.objects.count() == PodcastSourceMetadata.objects.count() == 1
    podcast = Podcast.objects.get()
    assert Episode.objects.count() == len(source.episodes)
    assert podcast.numchild == podcast.get_children().count() == len(source.episodes)
    assert importer.import_django_chat_source_data(source).episodes_created == 0
