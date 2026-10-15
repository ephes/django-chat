# Transcript glossary pilot

Gold data for correcting misheard names and technical terms in Django Chat
transcripts. The feature itself is generic and specified in django-cast
(`backlog/2026-10-15-transcript-glossary.md`); this page and
`data/transcript-glossary/gold_terms.json` hold the Django Chat-specific
measurement data it is verified against.

## What was counted (2026-10-15)

Six Django Chat episodes, transcribed by Voxhelm's Parakeet backend
(`parakeet-tdt-0.6b-v3`, parakeet-mlx 0.5.3, 600 s chunks with 30 s overlap,
local attention, sentences capped at 30 s), 55,202 words:

| key | episode |
| --- | --- |
| `ep205` | Django Developers Survey 2026 |
| `ep206` | Django on the Med |
| `ep219` | Hiring in 2026 - Jon Gould |
| `eric` | Django Deployments in 2025 - Eric Matthes |
| `guest1` | EuroPython 2026 - Mia Bajić |
| `guest2` | Deploy on Day One - Calvin Hendryx-Parker |

Candidates came from two sources: a fuzzy match of each episode's title,
show-note link texts and "by <Author>" phrases against the transcript, and a
local LLM (Qwen3.6-27B 4-bit) asked to flag misheard names and terms. Each
candidate was judged in its sentence. The 34 that context could not settle
were listened to by the maintainer: 8 were kept as errors, 17 were no error,
9 stayed unclear and were dropped.

Result: **179 wrong names and terms**, about 3 per 1,000 words.

| class | meaning | count |
| --- | --- | --- |
| `G` | spelling is in the episode's contributors or show notes | 92 |
| `K` | ecosystem term (tools, projects, events) | 71 |
| `O` | other people and places | 16 |

The count is recall-limited: errors that neither the fuzzy match nor the LLM
flagged are missing.

How the errors repeat (rows checked in this order, misspellings compared
case-insensitively):

| occurrence | count |
| --- | --- |
| variant of a credited contributor's name (`John`, `Mathis`, `Ereb`, `Mir`, `Hendricks Parker`) | 26 |
| the same misspelling occurs in another episode | 12 |
| the correct term occurs in another episode, misheard differently | 18 |
| the correct term occurs in only this episode | 123 |

Inside one episode the same error repeats ("John" for Jon 22 times, "Scaff"
for scaf 14 times): grouped by (episode, `target`) the 179 occurrences come
down to 95 decisions of the form "in this episode, this is spelled Y"; grouped
by (episode, case-folded `original`, `target`) they are 121.

## Files

`data/transcript-glossary/gold_terms.json`:

- `episodes`: per key the feed title, the feed `guid` and the sha256 of the
  raw transcript file the offsets refer to.
- `occurrences`: one entry per error with `id`, `episode`, `segment` (index
  into the raw transcript's segments), `start_ms`/`end_ms` of the segment,
  `segment_text` (the raw segment text, one sentence), `span` (character
  offsets of the error in `segment_text`), `original`, `target` (correct
  spelling), `class` and `evidence` (`context` or `listened`).

Only each error's own sentence is committed. The full raw transcripts are
kept privately on atlas (`~/data/transcript-glossary-pilot/<key>.asr.json`)
and are not part of this repository; the checksums in `episodes` tell whether
a local copy is the one the offsets were measured on.

## Using it

The django-cast spec scores each slice against this file per occurrence
(fixed, missed, wrongly changed) and per decision. Scoring a show-level list
must be leave-one-episode-out: build it from five episodes and score the
sixth, otherwise a list built from these very episodes looks far better
than it is.
