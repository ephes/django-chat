from pathlib import Path
from typing import Any

import pytest
from django.test import override_settings

from django_chat.imports import import_sample as importer


@pytest.mark.parametrize(
    "content",
    [
        b'{"id":"a","\\u0069d":"b"}',
        b'{"guid":"a","guid":"b"}',
        b'{"items":' + b"[" * 80 + b"0" + b"]" * 80 + b"}",
    ],
)
def test_ambiguous_or_deep_json_refuses(tmp_path: Path, content: bytes) -> None:
    (tmp_path / "source.json").write_bytes(content)
    with pytest.raises(ValueError, match="Fixture"):
        importer._read_json(tmp_path, "source.json")


def test_fixture_actual_bytes_are_bounded(tmp_path: Path, monkeypatch: Any) -> None:
    monkeypatch.setattr(importer, "TEXT_MAX_BYTES", 16, raising=False)
    (tmp_path / "source.json").write_bytes(b'{"id":"' + b"x" * 20 + b'"}')
    with pytest.raises(ValueError, match="Fixture"):
        importer._read_json(tmp_path, "source.json")


def test_fixture_special_file_refuses_without_blocking(tmp_path: Path) -> None:
    # A directory reproduces non-regular admission without hanging the old
    # unbounded reader. The FIFO subprocess regression below has a hard timeout.
    (tmp_path / "source.json").mkdir()
    with pytest.raises(ValueError, match="Fixture"):
        importer._read_json(tmp_path, "source.json")


def test_fixture_fifo_refuses_promptly(tmp_path: Path) -> None:
    import os
    import subprocess
    import sys

    os.mkfifo(tmp_path / "rss_feed.xml")
    code = """import django; django.setup()
from django_chat.imports.import_sample import load_sample_source_data
import sys
try:
    load_sample_source_data(sys.argv[1])
except ValueError:
    sys.exit(0)
sys.exit(1)
"""
    result = subprocess.run([sys.executable, "-c", code, str(tmp_path)], timeout=5, check=False)
    assert result.returncode == 0


def test_fixture_exact_byte_and_depth_limits_and_quoted_punctuation(
    tmp_path: Path, monkeypatch: Any
) -> None:
    content = b'{"items":' + b"[" * 63 + b'"[{\\""' + b"]" * 63 + b"}"
    (tmp_path / "source.json").write_bytes(content)
    monkeypatch.setattr(importer, "TEXT_MAX_BYTES", len(content))
    assert "items" in importer._read_json(tmp_path, "source.json")


def test_fixture_symlink_refuses_and_retains_target(tmp_path: Path) -> None:
    target = tmp_path / "target.json"
    target.write_bytes(b'{"id":"synthetic"}')
    (tmp_path / "source.json").symlink_to(target)
    with pytest.raises(ValueError, match="Fixture"):
        importer._read_json(tmp_path, "source.json")
    assert target.read_bytes() == b'{"id":"synthetic"}'


@pytest.mark.django_db
def test_fixture_refusal_has_no_import_effects(tmp_path: Path) -> None:
    from cast.models import Podcast
    from wagtail.images.models import Image

    (tmp_path / "rss_feed.xml").write_text(
        "<rss><channel><title>Synthetic podcast</title></channel></rss>"
    )
    (tmp_path / "simplecast_podcast.json").write_bytes(b'{"id":"synthetic","id":"other"}')
    with (
        override_settings(MEDIA_ROOT=tmp_path / "media"),
        pytest.raises(ValueError, match="duplicate"),
    ):
        importer.import_django_chat_sample(
            tmp_path, cover_image_downloader=lambda _: pytest.fail("not admitted")
        )
    assert not Podcast.objects.exists()
    assert not Image.objects.exists()
    assert not (tmp_path / "media").exists()
