"""Collect Django Chat transcript lines for use as English ham training data.

`Transcript.dote` is a `FileField`, not a JSON column, so reading it needs the
app's transcript storage configured — run this where the site runs (staging),
not against a bare local checkout.
"""

from __future__ import annotations

import json
from collections.abc import Iterator

from cast.models.transcript import Transcript


def iter_transcript_lines() -> Iterator[tuple[int, str]]:
    """Yield `(transcript_id, text)` for every non-empty DOTe line.

    Transcripts whose DOTe payload cannot be read are skipped; the caller is
    expected to surface the count so a silent shortfall is visible.
    """
    # ty cannot see the implicit manager on cast's Transcript model.
    queryset = Transcript.objects.exclude(dote="").exclude(dote=None).order_by(  # ty: ignore[unresolved-attribute]
        "id"
    )
    for transcript in queryset.iterator():
        try:
            with transcript.dote.open("rb") as handle:
                payload = json.load(handle)
        except (OSError, ValueError):
            continue
        for line in payload.get("lines", []):
            text = (line.get("text") or "").strip()
            if text:
                yield transcript.id, text


def unreadable_transcript_ids() -> list[int]:
    """Return the ids of transcripts whose DOTe payload could not be parsed."""
    unreadable: list[int] = []
    # ty cannot see the implicit manager on cast's Transcript model.
    queryset = Transcript.objects.exclude(dote="").exclude(dote=None).order_by(  # ty: ignore[unresolved-attribute]
        "id"
    )
    for transcript in queryset.iterator():
        try:
            with transcript.dote.open("rb") as handle:
                json.load(handle)
        except (OSError, ValueError):
            unreadable.append(transcript.id)
    return unreadable


def collect_transcript_lines() -> list[str]:
    """All DOTe transcript lines across every transcript, in transcript order."""
    return [text for _transcript_id, text in iter_transcript_lines()]
