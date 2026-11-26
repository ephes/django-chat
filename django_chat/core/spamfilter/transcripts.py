"""Collect Django Chat transcript lines for use as English ham training data.

`Transcript.dote` is a `FileField`, not a JSON column, so reading it needs the
app's transcript storage configured — run this where the site runs (staging),
not against a bare local checkout.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any, cast

from cast.models.transcript import Transcript


def iter_transcript_lines() -> Iterator[tuple[int, str]]:
    """Yield `(transcript_id, text)` for every non-empty DOTe line.

    Transcripts whose DOTe payload cannot be read are skipped; the command
    reports how many transcripts contributed lines.
    """
    # ty cannot see the implicit manager on cast's Transcript model.
    transcript_objects = cast(Any, Transcript).objects
    queryset = transcript_objects.exclude(dote="").exclude(dote=None).order_by("id")
    for transcript in queryset.iterator():
        try:
            with transcript.dote.open("rb") as handle:
                payload = json.load(handle)
        except OSError, ValueError:
            continue
        for line in payload.get("lines", []):
            text = (line.get("text") or "").strip()
            if text:
                yield transcript.id, text
