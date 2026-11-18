from __future__ import annotations

from io import StringIO
from pathlib import Path
from typing import Any
from unittest import mock

import pytest
from cast.models import Audio
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db.models.fields.files import FieldFile
from django.test import override_settings

CONTENT = b"synthetic mp3 bytes"


def _legacy_audio(title: str = "Synthetic") -> Audio:
    """An audio whose cached size predates django-cast's file-name binding."""
    user = get_user_model().objects.get_or_create(username="size-cache-editor")[0]
    audio = Audio(
        user=user,
        title=title,
        mp3=SimpleUploadedFile("synthetic.mp3", CONTENT, content_type="audio/mpeg"),
    )
    audio.save(duration=False, cache_file_sizes=False)
    Audio.objects.filter(pk=audio.pk).update(data={"size": {"mp3": len(CONTENT)}, "keep": 1})
    return Audio.objects.get(pk=audio.pk)


def _run(*args: str) -> str:
    out = StringIO()
    call_command("cache_django_chat_audio_sizes", *args, stdout=out)
    return out.getvalue()


@pytest.mark.django_db
def test_dry_run_counts_unbound_sizes_without_writing(tmp_path: Path) -> None:
    with override_settings(MEDIA_ROOT=tmp_path):
        audio = _legacy_audio()
        output = _run()

    assert "Dry-run audio size cache: audios=1, bound=0, unbound=1, updated=0" in output
    assert Audio.objects.get(pk=audio.pk).data == {"size": {"mp3": len(CONTENT)}, "keep": 1}


@pytest.mark.django_db
def test_write_binds_storage_size_to_file_name_and_is_idempotent(tmp_path: Path) -> None:
    with override_settings(MEDIA_ROOT=tmp_path):
        audio = _legacy_audio()
        output = _run("--write")
        second = _run("--write")

    stored = Audio.objects.get(pk=audio.pk)
    data: Any = stored.data
    assert "updated=1" in output
    assert data["size"] == {"mp3": len(CONTENT)}
    assert data["size_file_names"] == {"mp3": stored.mp3.name}
    assert data["keep"] == 1
    assert "bound=1, unbound=0, updated=0" in second


@pytest.mark.django_db
def test_write_reports_storage_failures_and_fails(tmp_path: Path) -> None:
    with override_settings(MEDIA_ROOT=tmp_path):
        first = _legacy_audio("First")
        second = _legacy_audio("Second")
        real_size = FieldFile.size

        def size(field_file: FieldFile) -> int:
            if field_file.instance.pk == first.pk:
                raise RuntimeError("storage unavailable")
            return real_size.fget(field_file)  # type: ignore[attr-defined]

        out = StringIO()
        with (
            mock.patch.object(FieldFile, "size", property(size)),
            pytest.raises(CommandError, match="1 audio file size"),
        ):
            call_command("cache_django_chat_audio_sizes", "--write", stdout=out)

    assert f"Failed: audio {first.pk} mp3" in out.getvalue()
    assert "RuntimeError" in out.getvalue()
    assert "size_file_names" not in Audio.objects.get(pk=first.pk).data
    assert "size_file_names" in Audio.objects.get(pk=second.pk).data


@pytest.mark.django_db
def test_write_skips_a_file_replaced_after_its_size_was_read(tmp_path: Path) -> None:
    with override_settings(MEDIA_ROOT=tmp_path):
        audio = _legacy_audio()
        real_size = FieldFile.size

        def size_then_replace(field_file: FieldFile) -> int:
            value = real_size.fget(field_file)  # type: ignore[attr-defined]
            Audio.objects.filter(pk=audio.pk).update(mp3="cast_audio/replacement.mp3")
            return value

        with mock.patch.object(FieldFile, "size", property(size_then_replace)):
            output = _run("--write")

    assert "updated=0, changed_meanwhile=1" in output
    assert "size_file_names" not in Audio.objects.get(pk=audio.pk).data


@pytest.mark.django_db
def test_dry_run_and_write_are_exclusive() -> None:
    with pytest.raises(CommandError, match="mutually exclusive"):
        _run("--dry-run", "--write")
