from __future__ import annotations

from io import StringIO
from pathlib import Path

import pytest
from django.core.management import call_command
from django.test import override_settings

from django_chat.imports.import_sample import DownloadedAudio, import_django_chat_sample
from django_chat.imports.performance import (
    format_catalog_performance_result,
    measure_catalog_performance,
)


@pytest.mark.django_db
def test_catalog_performance_measurement_reports_feed_and_list_metrics(
    tmp_path: Path,
) -> None:
    with override_settings(MEDIA_ROOT=tmp_path):
        import_django_chat_sample(copy_audio=True, audio_downloader=FakeAudioDownloader())
        result = measure_catalog_performance(host="testserver")

    assert result.feed.path == "/episodes/feed/podcast/mp3/rss.xml"
    assert result.feed.status_code == 200
    assert result.feed_item_count == 8
    assert result.feed.query_count >= 0
    assert result.episode_list.path == "/episodes/"
    assert result.episode_list.status_code == 200
    assert result.episode_list.query_count > 0

    output = format_catalog_performance_result(result)
    assert "Django Chat catalog performance measurement" in output
    assert "items=8" in output
    assert "Episode list:" in output


@pytest.mark.django_db
def test_catalog_performance_management_command_outputs_metrics(tmp_path: Path) -> None:
    with override_settings(MEDIA_ROOT=tmp_path):
        import_django_chat_sample(copy_audio=True, audio_downloader=FakeAudioDownloader())
        stdout = StringIO()
        call_command("measure_django_chat_catalog", "--host=testserver", stdout=stdout)

    output = stdout.getvalue()
    assert "Feed:" in output
    assert "items=8" in output
    assert "Episode list:" in output


class FakeAudioDownloader:
    def __call__(self, source_url: str) -> DownloadedAudio:
        content = f"fake audio bytes for {source_url}".encode()
        return DownloadedAudio(
            content=content,
            content_type="audio/mpeg",
            content_length=len(content),
            filename="sample.mp3",
        )
