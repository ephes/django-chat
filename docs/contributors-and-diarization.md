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
> rather than inlining the character in a `-c` string. The byte-for-byte match
> requirement applies **only to the label ↔ `display_name` pair** — that is what
> the sanitizer compares. Free-text fields such as `short_bio` are never matched
> against anything, so non-ASCII there is harmless; keep it ASCII only to dodge
> the shell-quoting trap, not for correctness (e.g. write "La Suite numerique" in
> the bio while the guest's `display_name` stays exactly as it must appear).

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

### 4+5 consolidated: one idempotent apply-and-seed script

In practice steps 4 and 5 are best run as a **single standalone `.py` on the
server**, driven by `sys.argv` so non-ASCII names and JSON mappings survive the
`ssh → bash → python` chain (note: `manage.py shell -c` does **not** forward
argv, so this must be a real script, not `-c`). It is idempotent —
`get_or_create` for the guest/assignments and a skip-if-exists guard for the
voice ref — so re-running is safe. Drop it at e.g. `/home/django-chat/diar_apply.py`:

```python
import sys; sys.path.insert(0, "/home/django-chat/site")
import os, json, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production"); django.setup()
from decimal import Decimal
from cast.models import Episode, Transcript, Contributor, EpisodeContributor, Audio
from cast.models.contributors import ContributorVoiceReference

# argv: <audio_id> '<mapping_json>' [<guest_slug> <Guest Name> <bio>]...
audio_id = int(sys.argv[1]); mapping = json.loads(sys.argv[2])
guests = [tuple(sys.argv[3:][i:i+3]) for i in range(0, len(sys.argv[3:]), 3)]

ep = Episode.objects.get(podcast_audio_id=audio_id)
will = Contributor.objects.get(slug="will-vincent")
carlton = Contributor.objects.get(slug="carlton-gibson")
assigns = [(will, EpisodeContributor.ROLE_HOST), (carlton, EpisodeContributor.ROLE_HOST)]
for slug, name, bio in guests:
    g, created = Contributor.objects.get_or_create(
        slug=slug, defaults=dict(display_name=name, visible=True,
                                 default_role="guest", short_bio=bio))
    if not created and g.display_name != name:
        print("WARN existing", slug, repr(g.display_name), "!=", repr(name))
    assigns.append((g, EpisodeContributor.ROLE_GUEST))
for c, role in assigns:
    EpisodeContributor.objects.get_or_create(episode=ep, contributor=c, role=role)

t = Transcript.objects.get(audio_id=audio_id); t.rewrite_speaker_labels(mapping)
print("labels:", t.get_speaker_labels(),
      "| visible:", [a.display_name for a in ep.visible_contributor_assignments])

def longest_run(pd, name, cap=30.0, min_len=8.0):
    best=None; i=0; n=len(pd)
    while i < n:
        if pd[i].get("speaker")==name and pd[i].get("start_ms") is not None:
            j=i
            while j+1<n and pd[j+1].get("speaker")==name and pd[j+1].get("end_ms") is not None: j+=1
            s=pd[i]["start_ms"]/1000.0; e=pd[j]["end_ms"]/1000.0
            if best is None or (e-s)>(best[1]-best[0]): best=(s,e)
            i=j+1
        else: i+=1
    if best is None or (best[1]-best[0])<min_len: return None
    return (round(best[0],3), round(min(best[1], best[0]+cap),3))

pd = t.podlove_data.get("transcripts", [])
for slug, name, bio in guests:  # guard is per (contributor, source_audio) — see note below
    c = Contributor.objects.get(slug=slug)
    if ContributorVoiceReference.objects.filter(contributor=c, source_audio_id=audio_id).exists():
        print("voiceref exists for", name); continue
    rng = longest_run(pd, name)
    if not rng: print("NO clean run for", name); continue
    ContributorVoiceReference.objects.create(
        contributor=c, source_audio=Audio.objects.get(pk=audio_id),
        start_seconds=Decimal(str(rng[0])), end_seconds=Decimal(str(rng[1])),
        status=ContributorVoiceReference.Status.APPROVED, consent_confirmed=True,
        title="seed %s" % name)
    print("seeded", name, rng)
```

Run it (only the title-mapped speakers; leave spurious/empty labels out so they
sanitize):

```bash
.venv/bin/python /home/django-chat/diar_apply.py 205 \
  '{"Speaker 1": "Will Vincent", "Speaker 2": "Samuel Paccoud", "Speaker 3": "Carlton Gibson"}' \
  samuel-paccoud "Samuel Paccoud" "DINUM; building La Suite, an open-source productivity suite"
```

It is a throwaway operator artifact (delete it after — it is not part of the
app), but recreating it each run is wasted effort; keep this copy.

> **Recurring guests accumulate a voice reference per episode.** The seed guard
> above is keyed on `(contributor, source_audio_id)`, **not** on the contributor
> alone — so passing an already-seeded guest (e.g. Jeff Triplett, who returns
> across episodes) for a *new* episode seeds a **second** reference from the new
> audio, because none exists for that audio yet. This is harmless — extra clean
> samples can only help the known-speaker engine, and references are private — so
> one-per-person is not required. If you want strictly one reference per person,
> omit the guest from the seeding step (or pre-check
> `ContributorVoiceReference.objects.filter(contributor=c).exists()`) when they
> already have one. Hosts are passed via the host block, never the guest list, so
> they are seeded exactly once regardless.

### 5b. Contributor links (strip anchors + `podcast:person href`)

Each `Contributor` has ordered `ContributorLink` rows (`service` ∈ {website,
github, mastodon, twitter, linkedin, youtube} + `url`). Per episode,
`EpisodeContributor.link` is an FK to one of that contributor's links — **the one
chosen surfaces as the contributor-strip anchor and the RSS
`<podcast:person href="…">`**. With no `EpisodeContributor.link`, the person tag
is emitted without `href` (still valid). So two steps: create the link, then
point the episode assignment at it.

Host-link standard (apply to **every** diarized episode, not just new ones):

- **Will Vincent** → `mastodon https://fosstodon.org/@wsvincent`
- **Carlton Gibson** → `mastodon https://chaos.social/@carlton`
  (an older `https://fosstodon.org/@carlton` is **wrong** — fix it)

Guest links: prefer **Mastodon**, else an authoritative website/profile from the
episode show notes (the episode page's external links are the best source),
transcript, or a web search. Examples used in the 2026-05-30 batch: Paolo
Melchiorre `fosstodon.org/@paulox`, Jeff Triplett `mastodon.social/@webology`,
Marlene Mhangami `fosstodon.org/@Marlene`, Tim Allen `fosstodon.org/@FlipperPA`,
Andrew Miller `indiehackers.social/@nanorepublica`, Roman Pronskiy
`phpc.social/@pronskiy`, and — where no Mastodon exists — Jacob Walls
`github.com/jacobtylerwalls`.

Mechanics (idempotent; `service`+`contributor` identify a link, so re-running
updates the URL in place — this is how the wrong Carlton link gets corrected):

```python
from cast.models import Episode, EpisodeContributor, Contributor, Transcript
from cast.models.contributors import ContributorLink

def ensure_link(c, service, url):  # get-or-create, update URL if changed
    link, created = ContributorLink.objects.get_or_create(
        contributor=c, service=service, defaults={"url": url})
    if not created and link.url != url:
        link.url = url; link.save(update_fields=["url"])
    return link

def set_ec_link(episode, contributor, link):
    EpisodeContributor.objects.filter(
        episode=episode, contributor=contributor).update(link=link)

# Host links across ALL diarized episodes (run after each new episode lands):
will = Contributor.objects.get(slug="will-vincent")
carlton = Contributor.objects.get(slug="carlton-gibson")
wl = ensure_link(will, "mastodon", "https://fosstodon.org/@wsvincent")
cl = ensure_link(carlton, "mastodon", "https://chaos.social/@carlton")
dia = [ep.pk for ep in Episode.objects.filter(live=True, podcast_audio__isnull=False)
       if (t := Transcript.objects.filter(audio=ep.podcast_audio).first()) and t.get_speaker_labels()]
EpisodeContributor.objects.filter(episode_id__in=dia, contributor=will).update(link=wl)
EpisodeContributor.objects.filter(episode_id__in=dia, contributor=carlton).update(link=cl)
```

A recurring guest's link is shared across all their episodes; set
`EpisodeContributor.link` on each of their assignments (e.g. Jeff Triplett on both
the survey and the DjangoCon-Europe-recap episodes).

### 6. Verify

Public checks (no auth):

```bash
BASE=https://djangochat.staging.django-cast.com
curl -s "$BASE/api/audios/podlove/<AUDIO>/post/<POST>/" | python3 -c \
 'import sys,json;d=json.load(sys.stdin);from collections import Counter;\
print(Counter(s.get("speaker") for s in d["transcripts"]));print([c["name"] for c in d["contributors"]])'
curl -s "$BASE/episodes/<slug>/transcript/" | grep -c "<Guest Name>"
```

RSS `podcast:person href` (the **podcast feed** is the `.xml`, not the
`/episodes/feed/` HTML subscribe page):

```bash
# Real podcast RSS with podcast:person tags:
curl -s "$BASE/episodes/feed/podcast/mp3/rss.xml" \
  | grep -oE '<podcast:person href="[^"]*" role="(host|guest)">[^<]*</podcast:person>' \
  | sort | uniq -c
# Expect host hrefs (Will=fosstodon, Carlton=chaos.social) on every diarized
# episode, and each guest carrying their chosen link.
```

Also confirm **no public `Speaker N` leaks**: in the Podlove API JSON above, the
speaker counter should contain only real names + possibly `None`/`""`
(sanitized), never `Speaker 1/2/…`.

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
- **The poll SSH session is the fragile part, not the run.** A long-lived
  `ssh … 'for i in …; do … sleep 60; done'` poll loop can be dropped by the
  remote host mid-run (`exit 255`, "Connection closed by remote host", "Broken
  pipe"). That kills only your *polling* connection — the `nohup`
  `generate_transcripts` lanes keep running server-side, unaffected. Reconnect
  and re-poll the DB; it is not a lost run.
- **A CLI poll-timeout is a distinct, retry-worthy failure — not the same as
  all-empty.** In a multi-`--audio-id` lane, one audio can fail with
  `error audio=<pk>: Timed out waiting for Voxhelm job <uuid>` (the lane prints
  `errors=1` and exits non-zero) while the other audios in that lane succeed.
  The timed-out audio writes **no `Transcript` row at all** — tell it apart from
  an all-empty diarization by the DB: *no row* = the CLI gave up waiting (the
  Voxhelm job may still be cooking), whereas a row with labels `{'': N}` = an
  all-empty diarizer outcome. Both are fixed the same way: a plain `--force`
  re-submit, which dedups by `task_ref` onto the still-running job and usually
  lands fast (worked example: audio 68, 2026-05-30 batch — timeout → no row →
  `--force` retry → 4 clean labels in ~6 min). Raising
  `CAST_VOXHELM_POLL_TIMEOUT` reduces these, but a slow/queued job can still
  outlast it, so expect the occasional one-off retry on a 20-episode bulk run.
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
- **A full sentence repeated on many 1.0s cues is an ASR loop, not a labeling
  bug** — fix lives in `../voxhelm`; see "Known transcript-quality issue: ASR
  repetition loops".
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

### Additional batch (2026-05-29) — eight more episodes, DB-only

A second pass diarized and labeled eight more previously-undiarized episodes
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
| `how-france-ditched-microsoft-samuel-paccoud` | 205 / 212 | Samuel Paccoud | Will self-ID + sponsor/outro; guest = DINUM / La Suite (French govt), massively dominant (1356 segs); Carlton = remaining host (Django-contribution advocacy). Added as a follow-on one-off. |

Host roles vary per episode (Will or Carlton may read the sponsor/do the intro),
so the **self-identification in the intro** ("I'm Will Vincent…" / "I'm Carlton
Gibson…") was the decisive anchor, corroborated by who addresses whom and
biography. Approved voice references seeded for all eight new guests.

> **All-empty diarization can be transient — retry before giving up.**
> `freelancing-community-andrew-miller` (audio 5) returned **all-empty speaker
> labels** (`{'': 689}`) on its first attempt and was provisionally dropped. A
> later `--force` re-run of the *same* audio produced **three clean labels**
> (Will, Carlton, Andrew Miller) and the episode was completed normally (see the
> 2026-05-30 batch below). So an all-empty result is **not necessarily
> recording-specific** — it can be a transient Voxhelm outcome. Re-run `--force`
> at least once before concluding an episode is undiarizable; only treat it as
> undiarizable if it repeats. (Sponsor is irrelevant either way:
> `inverting-the-testing-pyramid-brian-okken` shares the same "Six Feet Up"
> sponsor and diarized cleanly.)
>
> **Throughput note.** The Voxhelm deployment processes diarization jobs
> serially; ~10–15 min per ~1h episode under load. Running multiple
> `generate_transcripts` lanes does not parallelize the backend (jobs queue), but
> it does keep the work moving if one episode's job is slow. A 30-episode bulk run
> (audios 22–51, 2026-05-30) averaged **~8–10 min/episode, ~4 h total**, and
> progress was **bursty**: when several lanes hit long (~1 h) episodes at once,
> Voxhelm went ~15–20 min with **no** completions and then several landed close
> together. So "stuck for 15 minutes" is usually the normal inter-cluster gap, not
> a stall — confirm the lane PIDs are alive (`ps`) before assuming a hang.

### Bulk-transcribe first, label later

Transcription and labeling are **separable**. Running `generate_transcripts` with
diarization produces raw `Speaker N` labels; with no contributors assigned to the
episode, those labels **sanitize out of public output** (the episode renders as a
normal un-attributed transcript). So it is safe to bulk-diarize many episodes
first and do the identify→map→link→seed→verify pass later — the intermediate state
is never publicly wrong. The 2026-05-30 batch of 30 was a transcribe-only run
(raw labels, no contributors yet).

### Known transcript-quality issue: ASR repetition loops

Whisper (Voxhelm's ASR) sometimes **hallucinates a repetition loop** on long or
hard-to-transcribe audio: one short sentence repeated as dozens-to-hundreds of
**exact 1.0-second cues**. Worst observed: audio 205 (`how-france-ditched-microsoft`,
`"I think it's a good thing." ×558`) and audio 203 (`deploy-on-day-one…`, ×557) —
each ~45–50% of the transcript. Music/silence stretches also trigger short outro
loops (e.g. `"Aliens of Glee" ×176`).

- **It is an ASR (Voxhelm/Whisper) problem, not diarization or label-mapping.** The
  garbage text is in the stored `podlove_data` exactly as Voxhelm returned it;
  diarization just assigns speakers to the bogus cues (so the label may flip
  mid-loop, which looks wrong but is the labeler doing its job on bad text).
- **Detect it:**
  ```python
  from collections import Counter
  from cast.models import Transcript
  c = Counter((s.get("text") or "") for s in Transcript.objects.get(audio_id=PK).podlove_data["transcripts"])
  print(c.most_common(3))  # a long *sentence* repeated >=~30x = a loop
  ```
  A high count on short filler (`"Yeah."`, `"Okay."`) is normal speech; a high
  count on a full sentence is a hallucination loop.
- **Fix lives upstream in `../voxhelm`,** not in django-chat: pass anti-loop decoding
  to the ASR backends — `condition_on_previous_text=False` (mlx) / `--max-context 0`
  + `--suppress-nst` (whisper.cpp), gated behind `VOXHELM_MLX_CONDITION_ON_PREVIOUS_TEXT`,
  `VOXHELM_WHISPERCPP_MAX_CONTEXT`, `VOXHELM_WHISPERCPP_SUPPRESS_NST`. After that ships
  and is deployed to the Voxhelm host, **regenerate** affected episodes with `--force`
  (which renumbers `Speaker N`, so any existing label mapping must be redone).
- **Status (2026-05-30): the anti-loop fix is now DEPLOYED** to the Voxhelm host
  (Studio). So the regeneration step is unblocked — re-run `generate_transcripts
  --force` on the candidates below and confirm the loop is gone (re-run the
  Detect snippet; the top sentence-length cue should drop back to normal speech
  counts). None of the candidates are contributor-mapped yet, so the
  `Speaker N` renumbering caveat does not bite for this batch.

#### Staging regeneration candidates (re-scanned 2026-05-30, fix now deployed)

Read-only staging DB scan, exact normalized transcript cue counts. Re-confirmed
against all **73** current `Transcript` rows after the audios-52–71 batch landed:
**17 transcripts still carry an ASR repetition loop** (the list below is
unchanged from the first scan — the batch added no new loops beyond 52/57/62,
which were already flagged). Episodes without a transcript row are not assessed
(no artifact to regenerate yet).

The Voxhelm anti-loop fix is **now deployed** (Studio), so regenerate these now —
`generate_transcripts --force` per audio, then re-run the Detect snippet to
confirm the top sentence-length cue dropped to normal counts:

| audio/post | slug | top repeated cue |
| --- | --- | --- |
| 1 / 4 | `django-tasks-jake-howard` | `"I think it was a lot of fun."` ×72 |
| 15 / 17 | `ai-in-the-real-world-marlene-mhangami-tim-allen` | `"Aliens of Glee"` ×176 |
| 19 / 21 | `django-fellow-jacob-walls` | `"So he's already got 120 commits..."` ×49 |
| 22 / 24 | `django-deployments-in-2025-eric-matthes` | `"And then he's like, I'm going to do this."` ×95 |
| 23 / 25 | `event-sourcing-chris-may` | `"I think that's a really good point."` ×175 |
| 29 / 31 | `official-django-mongodb-backend-jib-adegunloye` | `"So it's that fine-tuning..."` ×50 |
| 33 / 35 | `pretix-raphael-michel` | `"it's not about reducing complexity..."` ×51 |
| 34 / 36 | `python-tooling-hynek-schlawack` | `"And I'm a fellow at the University of New York."` ×77 |
| 41 / 43 | `buttondown-justin-duke` | `"I'm going to hire this guy."` ×86 |
| 44 / 46 | `cal-uluahin-sonmez` | `"I think that's a really good point."` ×116 |
| 45 / 47 | `django-orm-simon-charette` | `"And then you've got these two kind of like layers."` ×352 |
| 48 / 50 | `geodjango-harout-boujakjian-and-andrew-hornstra` | `"we've been working on it for a long time..."` ×134 |
| 52 / 54 | `understand-django-matt-layman` | `"And so we did a lot of work..."` ×38 |
| 57 / 59 | `pycharms-year-of-django-paul-everitt` | `"I think it's a good thing."` ×195 |
| 62 / 64 | `django-deployments-eric-matthes-ep108-replay` | `"I think that's a good point."` ×346 |
| 203 / 209 | `deploy-on-day-one-calvin-hendryx-parker` | `"It's never been the forefront of my developer tool."` ×557 |
| 205 / 212 | `how-france-ditched-microsoft-samuel-paccoud` | `"I think it's a good thing."` ×558; also `"And I think that's the way we're doing it."` ×126 |

> **Scanner caveat — short loop cues slip a `>25`-char filter.** Audio 15
> (`ai-in-the-real-world-marlene-mhangami-tim-allen`) loops on the **14-char**
> cue `"Aliens of Glee" ×176` (a music/silence outro loop), so a detector that
> only flags sentence-length cues (`len(text) > 25`) misses it. It is a genuine
> loop and a regeneration candidate. When re-scanning, either drop the length
> floor to ~10 or eyeball `most_common(3)` per transcript; do not treat a
> `>25`-only scan returning 16 as "audio 15 is now clean".

Borderline, spot-check before deciding whether to regenerate: audio 14
(`django-60-natalia-bidart`, ×28), audio 20 (`djangocon-us-2025-recap`, ×20),
audio 37 (`thibaud-colas-2025-dsf-board-nominations`, ×28), and audio 47
(`the-future-of-python-deb-nicholson`, ×22).

### Additional batch (2026-05-30) — contributor links + seven more episodes

This batch added the **contributor-link layer** (see [§5b](#5b-contributor-links-strip-anchors--podcastperson-href))
and diarized seven more previously-undiarized episodes (five required + two
bonus), DB-only. Speaker identification used the intro self-ID as the primary
anchor; per-episode evidence below. All browser-verified (strip + player tab +
`/transcript/`), API-verified (no public `Speaker N`), and RSS-verified
(`podcast:person href`).

**Host links applied across all 22 diarized episodes:** Will →
`fosstodon.org/@wsvincent`, Carlton → `chaos.social/@carlton` (the prior wrong
`fosstodon.org/@carlton` corrected). RSS confirms 22× each host with `href`.

| Episode (audio/post) | Speaker→name evidence | Guest link |
| --- | --- | --- |
| freelancing-community-andrew-miller-seDEJ66s (5/8) | S2=Carlton self-ID ("Carlton Gibson, joined by Will"); S1=Will (sponsor+outro); S3=Andrew "Andy" Miller ("known as NanoRepublica"). **Retry succeeded** after a prior all-empty run. | mastodon `indiehackers.social/@nanorepublica` |
| ai-in-the-real-world-marlene-mhangami-tim-allen (15/17) | S2=Carlton self-ID; S1=Will (remaining host); S3=Marlene (self-intro, Microsoft/PSF/PyCon Africa); S4=Tim Allen (Wharton WRDS principal eng); S5 (31 segs) unmapped over-seg | Marlene mastodon `fosstodon.org/@Marlene`; Tim mastodon `fosstodon.org/@FlipperPA` |
| django-survey-2025-jeff-triplett (17/19) | S1=Will self-ID; S2=Jeff ("good to be back", DjangoCon/DEFNA, survey); S4=Carlton (Oracle/internals); S3 (17 segs) unmapped | mastodon `mastodon.social/@webology` (also set on his recap episode 205) |
| django-on-the-med-paolo-melchiorre (18/20) | S1=Will self-ID; S2=Paolo ("from Pescara"; "you and Carlton" 3rd-person); S3=Carlton (co-attended, Django-process) | mastodon `fosstodon.org/@paulox` |
| django-fellow-jacob-walls (19/21) | S1=Will self-ID; S2=Jacob (greets both hosts; "first few weeks as a fellow"); S3=Carlton (reads sponsor; "Django on the Med a week away"); S4/S5 unmapped | github `github.com/jacobtylerwalls` (no Mastodon) |
| djangocon-us-2025-recap (20/22) — **hosts-only** | S1=Will (outro signoff; "DjangoCon US which I was at"); S2=Carlton ("English revolutionary period…presbyter=elder", British); S3 (2 segs) unmapped. No guest. | — |
| php-web-frameworks-roman-pronskiy (21/23) — bonus | S2=Will self-ID; S1=Carlton (sponsor; PHP-evolution Qs; "I'm sure Will will…" 3rd-person); S3=Roman (dominant, "collaborate with Django/Python world") | mastodon `phpc.social/@pronskiy` |

Approved private voice references seeded for each new guest (Andrew, Marlene,
Tim, Paolo, Jacob, Roman; Jeff already had one). Spurious low-count and `""`
labels were left unmapped and sanitize out (verified: no public `Speaker N`).

> **All-empty diarization is sometimes transient.** `freelancing-community-andrew-miller`
> returned all-empty on the 2026-05-29 attempt but **3 clean labels on a
> `--force` retry** here — retry before declaring an episode undiarizable.

### Additional batch (2026-05-30) — twenty more episodes, transcribe-only

A bulk transcribe-with-diarization pass over the next 20 previously-undiarized
episodes: **audios 52–71** (2023-12-20 `understand-django-matt-layman` down to
2023-03-01 `dev-environments-calvin-hendryx-parker`), DB-only, no app-code change
or redeploy. Raw-label run only (per
[Bulk-transcribe first, label later](#bulk-transcribe-first-label-later)): each
audio set to `transcript_diarization_mode='enabled'` and run with
`generate_transcripts --force`, leaving generic `Speaker N` labels and **no
contributors assigned**, so nothing renders publicly until a later
identify→map→link→seed pass. Verified by per-episode
`Transcript.get_speaker_labels()` — all 20 non-empty (label counts 2–8; audio 56
`becoming-a-django-fellow-natalia-bidart` over-segmented to 8, audios 63/64 to 2).

- **Run shape:** 4 `nohup` lanes of 5 audios each (52–56 / 57–61 / 62–66 /
  67–71), tracked by polling `get_speaker_labels()` in the DB (not the buffered
  logs). Throughput matched the earlier note: ~8–10 min/episode, bursty.
- **One retry, no skips:** audio 68 (`being-a-productive-developer-nick-janetakis`)
  hit a CLI poll-timeout on its first lane pass (`errors=1`, **no transcript row
  written** — a timeout, not an all-empty diarization). A single `--force`
  re-submit landed it with 4 labels in ~6 min. No all-empty results occurred, so
  all 20 succeeded. (See the poll-timeout and dropped-poll-session gotchas above.)
- **ASR repetition loops to regenerate later** (acceptable for a transcribe-only
  run; see the staging regeneration-candidates table above): audio 62
  (`django-deployments-eric-matthes-ep108-replay`, ×346) and audio 57
  (`pycharms-year-of-django-paul-everitt`, ×195) are badly looped; audio 52
  (`understand-django-matt-layman`) has a minor loop (×38).

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
  then regenerate. Voice references are already seeded for both hosts and every
  diarized guest, so the payload is ready; today the engine returns no `speakers`
  artifact (see status note above).
- Verify/correct the best-effort host (Will vs Carlton) attributions by ear if
  precise per-segment accuracy matters; corrections are one-line
  `rewrite_speaker_labels` calls.
