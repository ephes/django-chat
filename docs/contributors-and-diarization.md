# Contributors and diarized speaker labels

How Django Chat renders episode contributors and how diarized transcript
speaker labels reach the public Podlove player and transcript detail page.

## django-cast dependency / source choice

Contributor snippets and the diarized speaker-label workflow are **not** in any
django-cast PyPI release (latest `0.2.57` lacks both). They ship only on the
`develop` branch, which the sibling `../python-podcast` site also tracks.

`pyproject.toml` therefore pins django-cast to the develop branch by commit:

```toml
[tool.uv.sources]
django-cast = { git = "https://github.com/ephes/django-cast", rev = "d6ce2c7980baaece847d8495d22832208cd73f88" }
```

That commit reports `cast.__version__ == "0.2.58"`. Bump the `rev` deliberately
when develop advances and re-run `uv sync` + `just manage migrate`.

### Migrations introduced by the upgrade

`just manage migrate` applies the following cast migrations cleanly (from
`0066`):

| Migration | Adds |
| --- | --- |
| `0066_contributor_contributorlink_episodecontributor` | `Contributor`, `ContributorLink`, `EpisodeContributor` models |
| `0067_voxhelmsettings_diarization_enabled` | per-site `VoxhelmSettings.diarization_enabled` |
| `0068_contributor_default_role` | `Contributor.default_role` |
| `0069_audio_transcript_diarization_mode` | per-audio `Audio.transcript_diarization_mode` (`inherit`/`enabled`/`disabled`) |
| `0070_contributorvoicereference` | known-speaker voice references (unused here) |
| `0071_transcript_speakers_and_more` | `Transcript.speakers` + speaker sanitization plumbing |

> **Known harmless warning.** `makemigrations cast` reports an unmade
> `0072_alter_..._template_base_dir` migration. django-cast generates this
> choices-only migration dynamically from `CAST_CUSTOM_THEMES` (Django Chat
> registers the `django_chat` theme). It is choices/validation-only, predates
> this upgrade, is identical on local and staging, and must **not** be written
> into the installed package. `just manage migrate` / `check` are clean.

## Editor workflow (Wagtail admin)

1. **Snippets → Contributors → Add**: set `display_name`, a unique `slug`,
   `visible` (globally hides from public pages/feeds when off), `default_role`
   (Host/Guest), optional avatar and short bio, and ordered links.
2. **Episode page → Contributors panel** (collapsed by default): add a
   *Contributor* inline row per host/guest, choose the role, and optionally pick
   a link to surface for that episode.

## Public rendering

- Episode detail pages render visible contributor assignments through
  django-cast's `cast/contributors.html` partial, included from
  `django_chat/templates/cast/django_chat/episode.html` between the player and
  the show notes. The theme styles `.episode-contributors*` in
  `site.css` (avatar/placeholder chips, name, role pill).
- The contributor **HTML strip never enters the index/list pages or the
  generated podcast RSS** because it is included only by the detail-only
  `episode.html` template. Feed item bodies render `post_body.html` (which does
  not include the partial) and the episode index uses its own card markup, so
  neither path can render the strip. (django-cast's own `post_body.html` also
  guards the include with `render_detail and not render_for_feed`, but
  django-chat does not route the contributor strip through that template.)
- The generated podcast RSS does gain one **additive, spec-compliant change**:
  django-cast emits a Podcasting 2.0 `<podcast:person role="..." href="...">Name
  </podcast:person>` tag per visible contributor, **only** on items whose
  episode has contributors assigned. Verified safe on staging: the channel and
  all episodes without contributors are byte-for-byte unchanged (item count and
  feed validity hold), and only `breaking-django` carries person tags. Regression
  coverage: `test_generated_feed_emits_podcast_person_only_for_episodes_with_contributors`.

## Diarized speaker labels

The public speaker label is **gated on contributors**. `cast.transcript_sanitization`
strips any Podlove/DOTe/WebVTT speaker label that does not exactly match the
`display_name` of a **visible Contributor assigned to the live episode**. This
applies identically to the Podlove player API and the transcript detail page, so
the credit list doubles as the public speaker allow-list.

The Podlove player API additionally returns a `contributors` array derived from
the (sanitized) speaker labels; the player resolves each segment's `speaker`
against it and renders the name.

### Generating a diarized transcript

Voxhelm credentials are rendered onto staging from SOPS
(`cast_voxhelm_api_base` / `cast_voxhelm_api_key`). The staging VPS reaches the
Voxhelm host over Tailscale. Diarization is **off by default**; enable it
per-audio (scoped, no global setting change):

```bash
# On the server, as the app user, with the env sourced:
python manage.py shell -c "from cast.models import Audio; a=Audio.objects.get(pk=<AUDIO_ID>); a.transcript_diarization_mode='enabled'; a.save(update_fields=['transcript_diarization_mode'])"
CAST_VOXHELM_POLL_TIMEOUT=7200 python manage.py generate_transcripts --audio-id <AUDIO_ID> --force
```

Voxhelm returns generic labels (`Speaker 1`, `Speaker 2`, …). Map them to the
real contributors so the labels survive sanitization:

1. Create/assign the matching visible Contributors to the episode.
2. Rewrite the raw labels to the contributor `display_name`s:
   ```python
   Transcript.objects.get(pk=<ID>).rewrite_speaker_labels(
       {"Speaker 1": "Will Vincent", "Speaker 2": "Carlton Gibson"}
   )
   ```
   (`rewrite_speaker_labels` rewrites Podlove `speaker`/`voice`, DOTe
   `speakerDesignation`, and WebVTT voice labels in place; the WebVTT generated
   here has no voice labels, so only Podlove + DOTe actually change.) The Wagtail
   transcript admin also offers a speaker→contributor mapping form for this step.

### Identifying who is who (Django Chat heuristics)

Diarization separates voices but does not name them, and it tends to lump the
fast host intro banter into one label. Reliable text-only cues for Django Chat:

- **The intro self-ID is the single most reliable host anchor — check it first.**
  Almost every episode opens with one host naming both: "I'm Will Vincent, joined
  by Carlton Gibson" or "I'm Carlton Gibson, joined as ever by Will Vincent." That
  one segment pins the speaker who says it (and tells you the co-host's name).
  Confirmed present in all 7 episodes of the 2026-05-29 additional batch; it never
  misled, unlike the sponsor cue below.
- **Will Vincent** reliably reads the **outro signoff** ("…djangochat.com, we're
  on YouTube, we'll see everyone next time / next year"). The label carrying that
  signoff is Will, in every episode observed.
- **The sponsor read is NOT a reliable Will cue — corroboration only.** Whoever
  reads the sponsor spot varies per episode: in the 2026-05-29 batch Carlton read
  it in 3 of 7 (audio 4, 10, 13). Do not infer "sponsor reader = Will"; trust the
  self-ID and outro signoff instead. (A pre-recorded ad read split into its own
  1–2-segment label is still left unmapped — see below.)
- The **guest** is named in the episode title (`Topic - Guest Name`), is
  introduced by name, and is usually the dominant non-host voice. A guest who
  thanks/names *both* hosts ("Thank you for having me, Carlton and Will") confirms
  they are neither host.
- The remaining substantive host label is **Carlton Gibson** (positively: he is
  British/Europe-based — "we live in Spain", "which side of the Atlantic" — and
  the Django Fellow; see biography cues below).
- **Direct address → next turn** is the single strongest cue when it exists. A
  host often names the person they are handing to ("Are you going to make the
  sprints, **John**?", "**John**, what do you think?"); the *next* guest turn is
  that person. (Mind the lag note below — the answer can land one segment late.)
- **Content / biography cues identify hosts too, not just by elimination.**
  Carlton, the Django Fellow, tells signature stories (e.g. running the "getting
  started contributing to Django" sprint workshops, Django Europe Copenhagen
  2019); a label carrying that biography is Carlton even before you eliminate.
  Guests betray themselves the same way (a PyCon co-chair talks venue/program;
  the "film nerd / Python in special effects" persona, etc.).
- Leave pre-recorded ad-only labels and spurious low-count labels (1–2 segments
  from diarizer over-segmentation) **unmapped** — with no matching contributor
  they are sanitized out of public output, which is preferable to a wrong name.
  An **empty speaker label (`""`)** is normal: the diarizer leaves gaps it can't
  attribute (this episode had 71 such segments). Never map `""` to a name; it
  carries no speaker and sanitizes out unnamed, which is correct.

Host (Will vs Carlton) identification from text alone is best-effort and can
occasionally swap; a swap is a one-line `rewrite_speaker_labels` fix.

> **Known limitation — labels can lag turn changes by a second or two.** Voxhelm
> labels whole multi-second ASR segments with a single dominant speaker, so a
> segment that straddles a fast exchange (e.g. a host's "Welcome, Mia" at the
> start of the guest's first segment) carries one label until the next segment
> boundary. The displayed speaker can therefore be approximate right at turn
> changes. This is transcription-backend segmentation granularity, not a
> django-chat or label-mapping issue, and re-mapping changes only *which* name a
> segment shows, not where boundaries fall. Documented upstream in django-cast:
> `docs/media/audio-and-transcripts.rst` ("Voxhelm Integration").

### Voice references and the known-speaker engine

Seed an approved `ContributorVoiceReference` source-range (≈30s clean solo
passage) per contributor so Voxhelm's known-speaker engine can auto-identify
them later. Source-ranges store only `source_audio` + start/end seconds (no
uploaded file), are **private** (never exposed publicly or committed), and must
be `status=APPROVED` + `consent_confirmed=True` to be usable:

```python
ContributorVoiceReference.objects.create(
    contributor=contrib, source_audio=audio,
    start_seconds=Decimal("136.4"), end_seconds=Decimal("166.4"),
    status=ContributorVoiceReference.Status.APPROVED, consent_confirmed=True,
)
```

`build_known_speaker_references(episode)` assembles the payload from the
episode's assigned contributors' approved references. With
`CAST_VOXHELM_KNOWN_SPEAKER_ENABLED=true`, `generate_transcripts` sends it to
Voxhelm, which returns a private `Transcript.speakers` suggestion sidecar;
`Transcript.apply_known_speaker_suggestions()` then writes the confident
suggestions into public Podlove/DOTe (Podlove/DOTe only — not WebVTT).

> **Status (2026-05-29): known-speaker auto-ID is blocked at the Voxhelm
> server.** A known-speaker regeneration of audio 1 sent a valid payload (Will,
> Carlton, Jake — one reference each) but Voxhelm returned **no `speakers`
> artifact** (empty suggestion sidecar), i.e. the `pyannote_known_speaker`
> engine is not active for this deployment. Enabling it requires Voxhelm-server
> changes (`VOXHELM_DIARIZATION_BACKEND=pyannote`, a Hugging Face token, the
> CloudFront media host allow-listed) plus `CAST_VOXHELM_KNOWN_SPEAKER_ENABLED`
> in the staging env — see python-podcast's known-speaker runbook. Until then,
> the manual label-mapping above is the working path; the seeded voice
> references are ready for when the engine is enabled.

## Operator runbook: diarizing additional episodes

End-to-end recipe for diarizing and labeling more episodes on staging. It is
written so a fresh agent (no prior session context) can pick the work up. All of
it is **staging-database data work** — no app-code change and no redeploy is
needed (code changes would need `just deploy-staging`; these steps do not).

### 0. Connecting and running management commands on staging

SSH works as `root` (the staging host's root shell is **fish**, so pipe a bash
script in). Run Django commands as the `django-chat` app user with the env
sourced. Reusable wrapper:

```bash
ssh -o BatchMode=yes root@djangochat.staging.django-cast.com 'bash -s' <<'EOF'
sudo -u django-chat bash -lc '
  cd /home/django-chat/site
  set -a; . ./.env 2>/dev/null; set +a
  export DJANGO_SETTINGS_MODULE=config.settings.production
  .venv/bin/python manage.py <command...>
'
EOF
```

- Site lives at `/home/django-chat/site`; services are `django-chat.service`
  (gunicorn) and `django-chat-db-worker.service` (transcript worker).
- Voxhelm creds come from SOPS into the env; the VPS reaches the Voxhelm host
  over Tailscale, so diarization works server-side. The CloudFront media host is
  already fetchable by Voxhelm (it fetched episode audio for diarization).

### 1. Pick episodes and enable per-audio diarization

List candidates and note `audio.pk`, the episode `pk` (post id), and the title
(the title encodes the guest(s) as `Topic - Guest` or `Topic - Guest A & Guest B`):

```python
from cast.models import Episode, Transcript
for ep in Episode.objects.filter(live=True, podcast_audio__isnull=False).order_by("-visible_date")[:8]:
    a = ep.podcast_audio
    print(ep.visible_date.date(), "audio", a.pk, "post", ep.pk,
          "t" if Transcript.objects.filter(audio=a).exists() else "-", "|", ep.title)
```

Enable diarization per audio (scoped; no global setting change):

```python
from cast.models import Audio
for pk in [<AUDIO_IDS>]:
    a = Audio.objects.get(pk=pk); a.transcript_diarization_mode = "enabled"
    a.save(update_fields=["transcript_diarization_mode"])
```

### 2. Generate diarized transcripts

Run in the background with a raised poll timeout (long episodes take minutes):

```bash
export CAST_VOXHELM_POLL_TIMEOUT=7200 CAST_VOXHELM_POLL_INTERVAL=5
nohup .venv/bin/python manage.py generate_transcripts \
  --audio-id A --audio-id B ... --force > /home/django-chat/diarize.log 2>&1 &
```

> **Gotcha — buffered log.** Under `nohup`, Python block-buffers stdout, so
> `diarize.log` stays empty until the process exits. Track progress via the DB
> instead: poll `Transcript.objects.get(audio_id=pk).get_speaker_labels()` until
> non-empty for each audio, or wait for the final `processed=...` line.

A ready remote poll loop (runs server-side, returns when labels land or the
process exits — a ~57-minute episode like audio 3 took ≈4 min / ~13 polls):

```bash
for i in $(seq 1 60); do
  out=$(.venv/bin/python manage.py shell -c \
    'from cast.models import Transcript; print(Transcript.objects.get(audio_id=<PK>).get_speaker_labels())' 2>/dev/null | tail -1)
  proc=$(ps aux | grep generate_transcripts | grep -v grep | wc -l)
  echo "poll $i: labels=$out proc=$proc"
  [ "$out" != "[]" ] && { echo READY; break; }
  [ "$proc" -eq 0 ] && { echo EXITED; break; }
  sleep 20
done
```

`--force` regenerates even if a transcript already exists. Diarization yields
generic labels `Speaker 1`, `Speaker 2`, …; some episodes over-segment into a
spurious extra label (1–2 segments) or a separate ad-reader voice, and segments
the diarizer can't attribute come back with an **empty speaker (`""`)** — both
are left unmapped and sanitize out (see step 3). A clean run can also yield
*exactly* one label per real voice (audio 3: 4 labels = Will, Carlton, 2 guests,
plus `""` gaps) — don't assume there is always a spurious label to discard.

### 3. Identify which label is which person

Pull evidence per transcript and map labels with the
[heuristics above](#identifying-who-is-who-django-chat-heuristics):

```python
from collections import Counter
from cast.models import Transcript
t = Transcript.objects.get(audio_id=<AUDIO_ID>)
pd = t.podlove_data.get("transcripts", [])
def row(s):  # segments key on start_ms (not "start"); text can be None
    return (round((s.get("start_ms") or 0) / 1000, 1), s.get("speaker"), (s.get("text") or "")[:90])
print("counts:", dict(Counter(s.get("speaker") for s in pd)))
for s in pd[:16]:  print(*row(s), sep=" | ")   # intro (host banter often lumped)
for s in pd[-10:]: print(*row(s), sep=" | ")   # outro (Will)
# get_speaker_samples() returns TranscriptSpeakerSample OBJECTS, not dicts —
# use attribute access, NOT .get(): `s.text` raises AttributeError as a dict key.
for label, samples in t.get_speaker_samples(limit=3).items():
    print("==", label, "=="); [print("  ", getattr(s, "text", str(s))[:200]) for s in samples]
# Targeted: grep a name and print a window around each hit to attribute turns:
for i, s in enumerate(pd):
    if "elaine" in (s.get("text") or "").lower():
        for j in range(max(0, i - 1), min(len(pd), i + 4)): print(*row(pd[j]), sep=" | ")
```

Anchors that work for Django Chat: **Will** = the sponsor/outro label; **guest**
= named in the title, dominant non-host, on-topic; **Carlton** = the remaining
substantive host (often via a signature biographical story, not just
elimination); **leave ad-only, 1–2-segment, and empty-string labels unmapped**.
The keyword-window grep above is the workhorse: a host's direct address
("John, what do you think?") pins the *next* guest turn to a name.

#### Two (or more) guests

When the title is `Topic - Guest A & Guest B`, expect four real voices (Will,
Carlton, A, B) and possibly 5–6 labels after over-segmentation. To separate the
two guests from each other:

- **Reciprocal naming is the most decisive cue, and it self-confirms.** Guests
  refer to each other by name: if label X says "**B** and I were at…" then X≠B,
  and if label Y says "echoing **A**'s comments" right after A's turn then Y≠A.
  Two such cross-references that don't contradict pin both guests without
  guessing from order. (Worked example: `Speaker 4` said "When **Elaine** and I
  were at scale…" → Speaker 4 = Jon; `Speaker 2` said it was "echoing **John's**
  comments" → Speaker 2 = Elaine. Mutually consistent, so neither is a guess.)
- The intro usually names them in order ("…joined by **A** and **B**"); the
  first new non-host voice after that is typically A. Treat this as weaker than
  reciprocal naming or a direct address — use it to corroborate, not to decide.
- Match each guest label to the **topic each speaks to** (e.g. one guest covers
  the conf program, the other covers tooling) using `get_speaker_samples`.
- By elimination: the two substantive labels that are neither the Will
  (outro/sponsor) label nor the Carlton label are the two guests.
- **Beware lumped vocatives.** A segment labeled X may *open* with the previous
  speaker's address to X ("…what did I miss, **Elaine**?") because Voxhelm tags a
  whole multi-second segment by its dominant voice and a fast hand-off straddles
  the boundary. So "the Elaine-labeled segment says 'Elaine'" does **not** mean
  Elaine is addressing herself — it is usually the other person handing to her.
  Trust the self-statements ("**B** and I", "echoing **A**") over who is *named*
  inside a segment.
- If two guest voices are genuinely indistinguishable from text, label the
  confident one and leave the other unmapped (sanitized out) rather than risk a
  wrong name — or label both best-effort and note it. A guest↔guest swap is a
  one-line `rewrite_speaker_labels` fix.

Create a `Contributor` for **each** guest and assign all of them to the episode.

### 4. Create/assign contributors and rewrite labels

```python
from cast.models import Episode, Transcript, Contributor, EpisodeContributor
will = Contributor.objects.get(slug="will-vincent")
carlton = Contributor.objects.get(slug="carlton-gibson")
ep = Episode.objects.get(podcast_audio_id=<AUDIO_ID>)
guest, _ = Contributor.objects.get_or_create(
    slug="<guest-slug>",
    defaults=dict(display_name="<Guest Name>", visible=True,
                  default_role="guest", short_bio="<role>"))
for c, role in [(will, EpisodeContributor.ROLE_HOST),
                (carlton, EpisodeContributor.ROLE_HOST),
                (guest, EpisodeContributor.ROLE_GUEST)]:
    EpisodeContributor.objects.get_or_create(episode=ep, contributor=c, role=role)
t = Transcript.objects.get(audio_id=<AUDIO_ID>)
t.rewrite_speaker_labels({"Speaker 1": "Will Vincent", "Speaker 3": "Carlton Gibson",
                          "Speaker 2": "<Guest Name>"})
print(t.get_speaker_labels(), [a.display_name for a in ep.visible_contributor_assignments])
```

> **Gotcha — exact match.** The sanitizer keeps a label only if it equals a
> visible contributor's `display_name` exactly. Spurious/ad labels left out of
> the mapping stay as `Speaker N` and are dropped from public output.
>
> **Gotcha — non-ASCII names.** Names like `Mia Bajić` get mangled by nested
> `ssh → bash → python` single-quoting. Use a Python unicode escape
> (`"Mia Bajić"`) or write a small `.py` file on the server and run it,
> rather than inlining the character in a `-c` string. The contributor
> `display_name` and the rewritten label must match byte-for-byte.

### 5. Seed voice references (voiceprints) — optional, for future known-speaker

For each contributor, store an approved private source-range into a clean solo
passage (~30s). Hosts only need seeding once (reuse across episodes); seed each
new guest from their own episode.

```python
from decimal import Decimal
from cast.models import Transcript, Contributor, Audio
from cast.models.contributors import ContributorVoiceReference

def longest_run(pd, name, cap=30.0, min_len=8.0):
    best=None; i=0; n=len(pd)
    while i < n:
        if pd[i].get("speaker")==name and pd[i].get("start_ms") is not None:
            j=i
            while j+1<n and pd[j+1].get("speaker")==name and pd[j+1].get("end_ms") is not None:
                j+=1
            s=pd[i]["start_ms"]/1000.0; e=pd[j]["end_ms"]/1000.0
            if best is None or (e-s)>(best[1]-best[0]): best=(s,e)
            i=j+1
        else: i+=1
    if best is None or (best[1]-best[0])<min_len: return None
    return (round(best[0],3), round(min(best[1], best[0]+cap),3))

def seed(slug, audio_pk, name):
    c=Contributor.objects.get(slug=slug); t=Transcript.objects.get(audio_id=audio_pk)
    rng=longest_run(t.podlove_data.get("transcripts",[]), name)
    if not rng: print("no clean run for", name); return
    ContributorVoiceReference.objects.get_or_create(
        contributor=c, source_audio=Audio.objects.get(pk=audio_pk),
        start_seconds=Decimal(str(rng[0])), end_seconds=Decimal(str(rng[1])),
        defaults=dict(status=ContributorVoiceReference.Status.APPROVED,
                      consent_confirmed=True, title="seed %s" % name))
```

Voice references are **private** (DB + protected storage only) — never commit,
expose, or serialize them. They are ready for the known-speaker engine but do
nothing until it is enabled (see status note above).

### 6. Verify

Public checks (no auth):

```bash
BASE=https://djangochat.staging.django-cast.com
curl -s "$BASE/api/audios/podlove/<AUDIO>/post/<POST>/" | python3 -c \
 'import sys,json;d=json.load(sys.stdin);from collections import Counter;\
print(Counter(s.get("speaker") for s in d["transcripts"]));print([c["name"] for c in d["contributors"]])'
curl -s "$BASE/episodes/<slug>/transcript/" | grep -c "<Guest Name>"
```

Browser-level (required as real evidence — route/text checks are not enough).
The parametrized helper `.playwright-verify/verify_speakers.py` (local,
git-ignored) takes a slug + expected names and asserts the contributor strip,
the **Podlove player transcript tab**, and the transcript detail page, saving
screenshots:

```bash
uv run python .playwright-verify/verify_speakers.py <slug> "Will Vincent" "Carlton Gibson" "<Guest>"
```

If the script is missing, recreate it from these Podlove selectors: click
`[data-django-chat-player-placeholder]`, get `podlove-player iframe` →
`content_frame()`, wait `#app.loaded`, click `[data-test="tab-trigger--transcripts"]`,
read `#tab-transcripts` text, and match names **case-insensitively** (Podlove
uppercases speaker names via CSS).

### Gotchas (consolidated)

- `nohup` buffers stdout — track diarization progress via the DB, not the log
  (ready poll loop in step 2).
- `--force` **overwrites** existing labels with a fresh diarization. If you test
  the known-speaker path on an already-labeled episode, **back up** the
  `podlove`/`dote`/`vtt` bytes first and restore on failure (the new run's
  `Speaker N` numbering differs, so you cannot just re-apply the old mapping).
- Non-ASCII names: escape or use a `.py` file (see step 4). For repeated
  evidence/apply work, a small standalone `.py` on the server
  (`sys.path.insert(0, "/home/django-chat/site"); django.setup()`) run with
  `.venv/bin/python script.py <audio_id> ...` reads `sys.argv` cleanly and avoids
  the `ssh → bash → python -c` quoting trap entirely (note: `manage.py shell -c`
  does **not** forward argv).
- **Killing the `generate_transcripts` CLI does not cancel the Voxhelm job.** The
  job keeps running server-side; the `django-chat-db-worker` can complete it and
  write the transcript even after you killed the foreground process (you may later
  find `TranscriptGeneration.status == "succeeded"` for an audio you thought you
  abandoned). Voxhelm also dedups by `task_ref` (`cast-audio-<id>-diarized`), so a
  `--force` re-submit of the same audio attaches to the existing job rather than
  duplicating it. Practical upshot: prefer waiting over killing; if you must kill
  to unblock the serial queue, re-check the DB before re-submitting.
- Sanitizer is exact-match; leave ad/spurious labels unmapped.
- **`get_speaker_samples()` returns `TranscriptSpeakerSample` objects, not
  dicts** — use `sample.text` (attribute), not `sample.get("text")`, which
  raises `AttributeError`. Likewise podlove segments key on `start_ms` (not
  `start`), and `text` may be `None` — guard with `(s.get("text") or "")`.
- **Empty speaker label `""` is normal** (diarizer gaps, not an error). Never
  map it; it carries no name and sanitizes out unnamed.
- **Lumped vocatives mislead.** A name spoken inside a segment can be the
  *previous* speaker's hand-off straddling the boundary, so "the X-labeled
  segment says X" is not self-identification. Trust self-statements ("B and I",
  "echoing A's comments") and host direct-address → next-turn over in-segment
  vocatives.
- `transcript_diarization_mode='enabled'` persists on the audio (shared across
  episodes that reuse it) — intended.
- **Use the real episode slug for browser verification.** Some slugs carry a
  random suffix (e.g. `django-20-years-later-adrian-holovaty-g7z78kc0`,
  `freelancing-community-andrew-miller-seDEJ66s`). Read it from the episode list
  (`Episode.objects...slug`); a guessed slug without the suffix 404s and the
  Playwright run fails on a missing `.episode-contributors`.

## Staging verification (2026-05-29)

Deployed via `just deploy-staging` (rsync of the local checkout, `uv sync`,
migrate, collectstatic, service restart).

Seven episodes are diarized and labeled (Will Vincent + Carlton Gibson +
guest(s)): `breaking-django` (hosts only) plus —
`deploy-on-day-one-calvin-hendryx-parker` (Calvin Hendryx-Parker),
`europython-2026-mia-baji` (Mia Bajić),
`djangocon-europe-recap-other-news-jeff-triplett` (Jeff Triplett),
`django-tasks-jake-howard` (Jake Howard),
`boost-your-github-dx-adam-johnson` (Adam Johnson), and the two-guest
`pycon-us-2026-elaine-wong-jon-banafato` (Elaine Wong & Jon Banafato — audio 3,
post 6). Approved voice references are seeded for both hosts and all seven
guests.

`pycon-us-2026-elaine-wong-jon-banafato` (2026-05-29) is the worked two-guest
example for the [Two (or more) guests](#two-or-more-guests) heuristics.
Diarization yielded exactly four real labels (no spurious/over-segmentation
labels; 71 segments came back with an empty speaker label and sanitize out
unnamed). Identification was text-defensible, not order-guessed:
`Speaker 1` → **Will Vincent** (sponsor spot + "I'm Will Vincent" + outro);
`Speaker 3` → **Carlton Gibson** (his signature Django-Europe-Copenhagen-2019
"getting started contributing to Django" sprint-workshop story);
`Speaker 4` → **Jon Banafato** (answers Will's direct "John, what do you think?"
cue, and says "When **Elaine and I** were at scale…", distinguishing himself
from Elaine); `Speaker 2` → **Elaine Wong** (says she is "echoing **John's**
comments" right after Jon's turn, plus a consistent film/special-effects
persona). Guest voice references were seeded from clean solo runs bounded by
Will on both sides (Elaine 460.2–490.2s, Jon 1860.7–1890.7s).

Browser-level evidence (Playwright DOM assertions + screenshots, see
`.playwright-verify/`, gitignored) confirmed on
`https://djangochat.staging.django-cast.com` for `breaking-django`,
`boost-your-github-dx-adam-johnson`,
`djangocon-europe-recap-other-news-jeff-triplett`, and
`pycon-us-2026-elaine-wong-jon-banafato`:

- Episode detail page renders the "Hosts and Guests" contributor strip.
- Podlove player **transcript tab** shows the speaker labels (Podlove uppercases
  them via CSS).
- The `/transcript/` detail page shows the speaker labels in the themed layout.

Public Podlove API + transcript-page checks pass for all seven episodes;
spurious ad/over-segmentation labels are correctly sanitized out.

### Additional batch (2026-05-29) — five more episodes, DB-only

A second pass diarized and labeled seven more previously-undiarized episodes
using only the staging-database runbook below (no app-code change, no redeploy).
Each was identified from transcript evidence (host self-IDs, sponsor/outro
reader, guest naming/biography — never order-guessed), labels rewritten via
`rewrite_speaker_labels`, a ~30s approved private voice reference seeded for each
new guest, and **browser-verified** (Playwright DOM assertions + screenshots on
the contributor strip, the Podlove player transcript tab, and the `/transcript/`
page):

| Episode (slug) | audio/post | Guest | Speaker→name evidence |
| --- | --- | --- | --- |
| `from-kenya-to-london-with-django-velda-kiara` | 4 / 7 | Velda Kiara | Will self-ID; Carlton "we live in Spain"; guest dominant + bio |
| `improving-django-adam-hill` | 10 / 12 | Adam Hill | Carlton self-ID "I'm Carlton Gibson"; Will outro signoff; guest = Django Brew host |
| `inverting-the-testing-pyramid-brian-okken` | 11 / 13 | Brian Okken | Will self-ID + sponsor/outro; Carlton "you host, Brian"; guest "Michael and I" (Python Bytes) |
| `django-60-natalia-bidart` | 14 / 16 | Natalia Bidart | Will self-ID + "emceeing"; guest = release manager (December); Carlton "side of the Atlantic" |
| `building-a-django-api-framework-faster-than-fastapi` | 12 / 14 | Farhan Ali Raza | Carlton self-ID; Will sponsor/outro; guest "following Carlton for years" + GSoC |
| `django-20-years-later-adrian-holovaty-g7z78kc0` | 16 / 18 | Adrian Holovaty | Will self-ID + sponsor/outro; guest = Django creator running Soundslice; a 5-segment `Speaker 4` over-segmentation label left **unmapped** (sanitizes out) |
| `from-bootcamp-to-project-manager-keanya-phelps` | 13 / 15 | Keanya Phelps | Will self-ID + outro; guest names both hosts ("Carlton and Will"); Carlton = remaining host (sponsor reader) by elimination + Will's 3rd-person "Carlton was in the audience" |

Host roles vary per episode (Will or Carlton may read the sponsor/do the intro),
so the **self-identification in the intro** ("I'm Will Vincent…" / "I'm Carlton
Gibson…") was the decisive anchor, corroborated by who addresses whom and
biography. Approved voice references seeded for all five new guests.

> **Not every episode diarizes.** `freelancing-community-andrew-miller`
> (audio 5) was attempted and **dropped**: Voxhelm completed the job but returned
> **all-empty speaker labels** (`{'': 689}`) — no speaker separation at all, so
> there were no `Speaker N` labels to map. Left unlabeled with no contributors
> (sanitizes to a normal undiarized transcript). This is recording-specific, not
> a sponsor or pipeline issue (`inverting-the-testing-pyramid-brian-okken` uses
> the same "Six Feet Up" sponsor and diarized cleanly).
>
> **Throughput note.** The Voxhelm deployment processes diarization jobs
> serially; ~10–15 min per ~1h episode under load. Running multiple
> `generate_transcripts` lanes does not parallelize the backend (jobs queue), but
> it does keep the work moving if one episode's job is slow.

## Operational follow-ups

- Diarization stays off by default. To diarize more episodes, repeat the
  per-audio `transcript_diarization_mode='enabled'` + `generate_transcripts`
  + label-mapping steps, or set `CAST_VOXHELM_DIARIZATION_ENABLED` site-wide via
  `VoxhelmSettings` / env once a broad rollout is desired.
- Contributor avatars are optional; the partial falls back to an initial chip.
  Add avatars in Wagtail when host/guest portraits are available.
- **Enable known-speaker auto-ID** to remove the manual label-mapping step:
  configure the Voxhelm server (`pyannote` backend + HF token + CloudFront host
  allow-listed) and set `CAST_VOXHELM_KNOWN_SPEAKER_ENABLED` in the staging env,
  then regenerate. Voice references are already seeded for both hosts and the
  five guests, so the payload is ready; today the engine returns no `speakers`
  artifact (see status note above).
- Verify/correct the best-effort host (Will vs Carlton) attributions by ear if
  precise per-segment accuracy matters; corrections are one-line
  `rewrite_speaker_labels` calls.
