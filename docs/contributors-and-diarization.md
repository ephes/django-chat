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

## Staging verification (2026-05-29)

Deployed via `just deploy-staging` (rsync of the local checkout, `uv sync`,
migrate, collectstatic, service restart). Reference episode:
`breaking-django` (audio 202), diarized into 2 speakers and mapped to
**Will Vincent** + **Carlton Gibson**.

Browser-level evidence (Playwright DOM assertions + screenshots, see
`.playwright-verify/`, gitignored) confirmed on
`https://djangochat.staging.django-cast.com`:

- Episode detail page renders the "Hosts and Guests" contributor strip.
- Podlove player **transcript tab** shows the speaker labels (Podlove uppercases
  them via CSS).
- `/episodes/breaking-django/transcript/` shows the speaker labels in the
  themed transcript layout.

## Operational follow-ups

- Diarization stays off by default. To diarize more episodes, repeat the
  per-audio `transcript_diarization_mode='enabled'` + `generate_transcripts`
  + label-mapping steps, or set `CAST_VOXHELM_DIARIZATION_ENABLED` site-wide via
  `VoxhelmSettings` / env once a broad rollout is desired.
- Contributor avatars are optional; the partial falls back to an initial chip.
  Add avatars in Wagtail when host/guest portraits are available.
- Known-speaker voice references (`ContributorVoiceReference`, migration `0070`)
  are available upstream but unused here; revisit if automatic speaker
  identification is wanted instead of manual label mapping.
