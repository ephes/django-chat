from __future__ import annotations

import io
from pathlib import Path
from typing import Any, cast

import pytest
from cast.models import Episode, Podcast
from django.db import transaction
from django.test import override_settings
from PIL import Image
from wagtail.images.models import Image as WagtailImage

from django_chat.imports.import_sample import import_django_chat_sample


def artwork(*, animated: bool = False) -> bytes:
    with io.BytesIO() as output:
        with Image.new("RGB", (4, 4)) as image:
            if animated:
                with Image.new("RGB", (4, 4), "red") as second:
                    image.save(output, "GIF", save_all=True, append_images=[second])
            else:
                image.save(output, "PNG")
        return output.getvalue()


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_cover_object_unwinds_later_catalog_failure(tmp_path: Path, monkeypatch: Any) -> None:
    sentinel = tmp_path / "shared.png"
    sentinel.write_bytes(b"existing shared cover")

    def fail(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("episode save failed")

    monkeypatch.setattr(Episode, "save", fail)
    with (
        override_settings(MEDIA_ROOT=tmp_path),
        pytest.raises(RuntimeError, match="episode save failed"),
    ):
        import_django_chat_sample(cover_image_downloader=lambda _: artwork())
    assert list(path for path in tmp_path.rglob("*") if path.is_file()) == [sentinel]
    assert not WagtailImage.objects.exists()
    assert not Podcast.objects.exists()


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_cover_refuses_caller_owned_transaction_before_storage(tmp_path: Path) -> None:
    with (
        override_settings(MEDIA_ROOT=tmp_path),
        transaction.atomic(),
        pytest.raises(RuntimeError, match="durable"),
    ):
        import_django_chat_sample(cover_image_downloader=lambda _: artwork())
    assert not any(path.is_file() for path in tmp_path.rglob("*"))


@pytest.mark.django_db
@pytest.mark.parametrize("animated", [False, True])
def test_cover_admission_precedes_wagtail_save(
    tmp_path: Path, monkeypatch: Any, animated: bool
) -> None:
    import django_chat.imports.import_sample as importer

    # Exercise a small explicit limit with tiny, synthetic encoded images.
    monkeypatch.setattr(importer, "ARTWORK_MAX_PIXELS", 15, raising=False)
    if animated:
        monkeypatch.setattr(importer, "ARTWORK_MAX_PIXELS", 16)
    saved = []
    original_save = WagtailImage.save

    def save(self: Any, *args: Any, **kwargs: Any) -> Any:
        saved.append(self)
        return original_save(self, *args, **kwargs)

    monkeypatch.setattr(WagtailImage, "save", save)
    with override_settings(MEDIA_ROOT=tmp_path), pytest.raises(ValueError, match="Artwork"):
        import_django_chat_sample(cover_image_downloader=lambda _: artwork(animated=animated))
    assert not saved
    assert not Podcast.objects.exists()
    assert not any(path.is_file() for path in tmp_path.rglob("*"))


@pytest.mark.django_db
def test_episode_conflicting_identities_roll_back_catalog() -> None:
    from dataclasses import replace

    from django_chat.imports.import_sample import (
        import_django_chat_source_data,
        load_sample_source_data,
    )
    from django_chat.imports.models import EpisodeSourceMetadata

    result = import_django_chat_sample()
    source = load_sample_source_data()
    first, second = source.episodes[:2]
    changed = replace(
        first, simplecast_episode_id=second.simplecast_episode_id, title="Conflicting update"
    )
    before = list(EpisodeSourceMetadata.objects.values())
    with pytest.raises(ValueError, match="identity"):
        import_django_chat_source_data(replace(source, episodes=(changed,)))
    assert list(EpisodeSourceMetadata.objects.values()) == before
    assert Episode.objects.get(pk=result.episodes[0].pk).title == first.title


@pytest.mark.django_db
def test_episode_slug_cannot_adopt_another_strong_identity() -> None:
    from dataclasses import replace

    from django_chat.imports.import_sample import (
        import_django_chat_source_data,
        load_sample_source_data,
    )

    import_django_chat_sample()
    source = load_sample_source_data()
    changed = replace(
        source.episodes[0], matching_key="guid:new", rss_guid="new", simplecast_episode_id="new-id"
    )
    with pytest.raises(ValueError, match="identity"):
        import_django_chat_source_data(replace(source, episodes=(changed,)))


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_cover_cleanup_uses_storage_returned_key(tmp_path: Path, monkeypatch: Any) -> None:
    from django.core.files.storage import FileSystemStorage

    class RenamingStorage(FileSystemStorage):
        def _save(self, name: str, content: Any) -> str:
            return super()._save("returned/cover.png", content)

    storage = RenamingStorage(location=tmp_path)
    field = cast(Any, WagtailImage)._meta.get_field("file")
    monkeypatch.setattr(field, "storage", storage)

    def fail(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("image row failed")

    monkeypatch.setattr(WagtailImage, "save", fail)
    with pytest.raises(RuntimeError, match="image row failed"):
        import_django_chat_sample(cover_image_downloader=lambda _: artwork())
    assert not storage.exists("returned/cover.png")
    assert not any(path.is_file() for path in tmp_path.rglob("*"))


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_cover_cleanup_includes_outer_commit_failure(tmp_path: Path, monkeypatch: Any) -> None:
    from django.db import DatabaseError, connection

    def fail() -> None:
        raise DatabaseError("catalog commit failed")

    with monkeypatch.context() as patch, override_settings(MEDIA_ROOT=tmp_path):
        patch.setattr(connection, "commit", fail)
        with pytest.raises(DatabaseError, match="catalog commit failed"):
            import_django_chat_sample(cover_image_downloader=lambda _: artwork())
    assert not WagtailImage.objects.exists()
    assert not Podcast.objects.exists()
    assert not any(path.is_file() for path in tmp_path.rglob("*"))


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_prior_cover_survives_failed_reimport(tmp_path: Path, monkeypatch: Any) -> None:
    with override_settings(MEDIA_ROOT=tmp_path):
        first = import_django_chat_sample(cover_image_downloader=lambda _: artwork())
        cover = cast(Any, first.podcast).cover_image
        assert (cover.width, cover.height) == (4, 4)
        before = cover.file.read()
        cover.file.close()

        def fail(*args: Any, **kwargs: Any) -> None:
            raise RuntimeError("episode update failed")

        # Retain a hand-created/adopted podcast's cover too, even when no
        # PodcastSourceMetadata row exists at preflight time.
        first.podcast_metadata.delete()
        monkeypatch.setattr(Episode, "save", fail)
        with pytest.raises(RuntimeError, match="episode update failed"):
            import_django_chat_sample(
                cover_image_downloader=lambda _: pytest.fail("existing cover")
            )
        first.podcast.refresh_from_db()
        assert cast(Any, first.podcast).cover_image_id == cover.pk
        cover.file.open("rb")
        assert cover.file.read() == before
        cover.file.close()


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_cover_survives_callback_failure_after_confirmed_commit(
    tmp_path: Path, monkeypatch: Any
) -> None:
    original = Episode.save

    def fail() -> None:
        raise RuntimeError("post-commit callback failed")

    def save(self: Any, *args: Any, **kwargs: Any) -> Any:
        result = original(self, *args, **kwargs)
        transaction.on_commit(fail)
        return result

    monkeypatch.setattr(Episode, "save", save)
    with override_settings(MEDIA_ROOT=tmp_path):
        with pytest.raises(RuntimeError, match="callback"):
            import_django_chat_sample(cover_image_downloader=lambda _: artwork())
        cover = cast(Any, Podcast.objects.get()).cover_image
        assert WagtailImage.objects.filter(pk=cover.pk).exists()
        assert cover.file.storage.exists(cover.file.name)


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_cover_unwinds_explicit_rollback(tmp_path: Path, monkeypatch: Any) -> None:
    def roll_back(*args: Any) -> None:
        transaction.set_rollback(True)

    monkeypatch.setattr(
        "django_chat.imports.import_sample._update_podcast_automatic_numbering", roll_back
    )
    with (
        override_settings(MEDIA_ROOT=tmp_path),
        pytest.raises(RuntimeError, match="marked for rollback"),
    ):
        import_django_chat_sample(cover_image_downloader=lambda _: artwork())
    assert not WagtailImage.objects.exists()
    assert not any(path.is_file() for path in tmp_path.rglob("*"))
