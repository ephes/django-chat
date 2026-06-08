"""Re-seed a reproducible diarized-transcript demo for the custom audio player.

The custom player groups a transcript by speaker (a heading per speaker run, a
muted time anchor only at run starts) only when the transcript cues carry public
speaker labels. The imported ``django-tasks-jake-howard`` transcript has no
per-cue speaker data, so the panel renders unlabelled (a timestamp on every
line). This command makes a representative diarized state **reproducible and
committed** (no reliance on hand-injected dev-DB data): it assigns the episode's
three visible contributors and writes deterministic, block-based speaker labels
onto the transcript cues.

It is idempotent and demo-only — the speaker runs are synthetic (a seeded,
block round-robin over the contributors), intended to exercise the speaker-run
rendering, not to claim real diarization. Run it against a local dev database:

    just manage seed_django_chat_diarized_demo

then open ``/episodes/django-tasks-jake-howard/`` and the transcript panel shows
``Will Vincent`` / ``Carlton Gibson`` / ``Jake Howard`` headings with sparse
timestamps. Public speaker labels stay gated on the visible contributors via
``cast.transcript_sanitization``, so a label only survives if its contributor is
assigned and visible.
"""

from __future__ import annotations

import json
import random
from typing import Any

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError

DEFAULT_SLUG = "django-tasks-jake-howard"
# (display_name, slug) for the three on-mic contributors, in speaking order.
DEMO_CONTRIBUTORS: tuple[tuple[str, str], ...] = (
    ("Will Vincent", "will-vincent"),
    ("Carlton Gibson", "carlton-gibson"),
    ("Jake Howard", "jake-howard"),
)
# Fixed seed so the synthetic speaker runs are identical on every run/machine.
SEED = 20260418
MIN_RUN = 3
MAX_RUN = 9


class Command(BaseCommand):
    help = "Re-seed a reproducible diarized-transcript demo (contributors + block speaker labels)."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--slug",
            default=DEFAULT_SLUG,
            help=f"Episode slug to seed (default: {DEFAULT_SLUG}).",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        # Imported lazily so the command module loads without the DB configured.
        from cast.models import (
            Contributor,
            Episode,  # noqa: F401  (ensures cast app is ready)
            EpisodeContributor,
        )

        slug = options["slug"]
        episode = self._get_episode(slug)
        audio = getattr(episode, "podcast_audio", None)
        if audio is None:
            raise CommandError(f"Episode '{slug}' has no podcast_audio.")
        transcript = getattr(audio, "transcript", None)
        if transcript is None or not getattr(transcript, "podlove", None):
            raise CommandError(
                f"Episode '{slug}' has no Podlove transcript file. "
                "Import a transcript first (e.g. `just import-staging-transcripts`)."
            )

        contributors = self._ensure_contributors(episode, Contributor, EpisodeContributor)
        labelled = self._label_transcript(transcript, [name for name, _ in DEMO_CONTRIBUTORS])

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded diarized demo for '{slug}': {len(contributors)} visible contributors, "
                f"{labelled} cues labelled across speaker runs."
            )
        )

    def _get_episode(self, slug: str) -> Any:
        from cast.models import Episode

        episode = Episode.objects.filter(slug=slug).first()
        if episode is None:
            raise CommandError(f"No episode with slug '{slug}'. Import the catalog/sample first.")
        return episode

    def _ensure_contributors(
        self, episode: Any, contributor_model: Any, episode_contributor_model: Any
    ) -> list[Any]:
        created: list[Any] = []
        for sort_order, (display_name, slug) in enumerate(DEMO_CONTRIBUTORS):
            contributor, _ = contributor_model.objects.get_or_create(
                slug=slug,
                defaults={"display_name": display_name, "visible": True},
            )
            # Keep the demo contributors visible + named even if a prior row existed.
            changed = False
            if contributor.display_name != display_name:
                contributor.display_name = display_name
                changed = True
            if not contributor.visible:
                contributor.visible = True
                changed = True
            if changed:
                contributor.save()
            episode_contributor_model.objects.get_or_create(
                episode=episode,
                contributor=contributor,
                defaults={"role": episode_contributor_model.ROLE_HOST, "sort_order": sort_order},
            )
            created.append(contributor)
        return created

    def _label_transcript(self, transcript: Any, speakers: list[str]) -> int:
        with transcript.podlove.open("r") as handle:
            data = json.load(handle)
        segments = data.get("transcripts")
        if not isinstance(segments, list) or not segments:
            raise CommandError("Transcript file has no 'transcripts' segments to label.")

        rng = random.Random(SEED)
        index = 0
        speaker_cursor = 0
        labelled = 0
        while index < len(segments):
            run_length = rng.randint(MIN_RUN, MAX_RUN)
            speaker = speakers[speaker_cursor % len(speakers)]
            for offset in range(run_length):
                position = index + offset
                if position >= len(segments):
                    break
                segment = segments[position]
                if isinstance(segment, dict):
                    segment["speaker"] = speaker
                    segment["voice"] = speaker
                    labelled += 1
            index += run_length
            speaker_cursor += 1

        # Overwrite the file in place at its existing path (delete-then-save keeps
        # FieldFile.save from appending a uniqueness suffix), so re-running the
        # command stays idempotent and does not orphan the prior file.
        name = transcript.podlove.name
        storage = transcript.podlove.storage
        if storage.exists(name):
            storage.delete(name)
        storage.save(name, ContentFile(json.dumps(data, ensure_ascii=False).encode("utf-8")))
        return labelled
