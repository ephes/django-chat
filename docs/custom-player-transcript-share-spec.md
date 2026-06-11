# Custom Player Transcript and Share Spec

Research and acceptance criteria for bringing the django-cast custom audio
player branch back to the transcript/share behavior Django Chat already had on
staging with the Podlove player.

> **Status: implemented on `feat/custom-player` (2026-06-08).** All acceptance
> criteria below are met. Generic behavior (sparse labelled timestamps, loading
> spinner + `aria-busy`, spring reveal honoring `prefers-reduced-motion`, the
> demoted icon-only keyboard-cues toggle, and a `data-share="none"` transport
> opt-out) landed upstream in django-cast with vitest + pytest coverage; Django
> Chat bumped its pinned django-cast rev, opted the in-transport share button out,
> replaced the under-player full-width hairline with a grid-aligned separator, and
> added a contributor-backed diarized browser fixture. The custom player remains a
> dev preview (`CAST_AUDIO_PLAYER="custom"` in `config/settings/local.py`);
> staging and production kept the Podlove player at the time of this snapshot.
> Since 2026-06-11 staging deploys with the custom player
> (`django_chat_audio_player: "custom"` in `deploy/group_vars/staging.yml`);
> production keeps Podlove until host sign-off, so the Podlove-oriented
> host-review / staging-differences / css-architecture / README docs still
> describe the production player.

> **Addendum (2026-06-11): historical snapshot — the as-built transcript moved
> on.** This spec is the 2026-06-08 acceptance snapshot; do not treat its
> detailed timestamp treatment as current. The "muted time anchor at speaker-run
> starts" plan was superseded by a beauty/UX review round (django-cast
> `1ad2748e`): speaker runs now open with a heading row (initial chip, name, and
> the run's timestamp; time-only anchors for speakerless runs) and the per-cue
> gutter timestamps are fully hidden in labelled mode. The same round replaced
> the current-cue underline band with an accent-border + tint highlight, added
> follow-along look-ahead via `scroll-margin`, instant far jumps, and
> search-suspends-follow. Current behavior is documented in
> [`docs/implementation-status.md`](implementation-status.md) and the django-cast
> 0.2.59 release notes.

## Research Snapshot

Compared with Playwright on 2026-06-08:

- Local branch:
  `http://localhost:8000/episodes/django-tasks-jake-howard/`
- Staging baseline:
  `https://djangochat.staging.django-cast.com/episodes/django-tasks-jake-howard/`
- Screenshots captured under `.playwright-verify/player-research/`.

Observed local custom-player behavior:

- The custom transcript panel lazy-loads 986 cues from
  `/api/audios/1/player-transcript/?post_id=4`.
- While cues load, the opened transcript panel currently shows plain loading
  text. The control looks idle even though the transcript request is in flight.
- The first cues render with visible per-line timestamps (`0:00`, `0:05`,
  `0:15`, ...), which makes the transcript feel more mechanical than staging.
- The same local endpoint returns `speaker: ""` for the initial cues, so
  `.cast-transcript__speaker` headings never render.
  django-cast at pin `66961f...` already renders speaker headings when cues
  carry speaker labels, so this observation may be local data state rather than
  a rendering bug.
- The `Transcript` toggle reads as a large standalone button between the player
  and the horizontal rule, rather than as the header for an attached transcript
  panel.
- The page shows two share controls: the custom player's in-transport
  `.cast-player__share` button and the Django Chat sidebar `Share` rail item.
- The sidebar share modal already integrates with the custom player:
  after seeking to 21 seconds, `cast-audio-player.getShareState()` returned
  `{currentTime: 21, duration: 4663, audioId: 1}` and the site modal opened
  with `Start at` checked, `0:21`, and a share URL ending in `?t=21`.
- The transcript toolbar button labelled `Tab cues` toggles whether transcript
  cue buttons are reachable by repeated Tab key presses. It sets
  `tabIndex=0` on cue buttons, persists the choice in `localStorage` as
  `cast-transcript-tabbable`, and exposes `aria-label="Keyboard-navigable cues"`.
  The visible label does not explain this.

Observed staging Podlove behavior:

- The Podlove API for the same episode returns speaker metadata on transcript
  segments, for example `speaker: "Carlton Gibson"` and `voice: "Carlton Gibson"`.
- The transcript tab renders speaker runs with visible speaker headings such as
  `CARLTON GIBSON`, `WILL VINCENT`, and `JAKE HOWARD`.
- Continuation lines are visually grouped under the speaker instead of exposing
  a strong timestamp on every line.
- The staging page has only the Django Chat page-level share entry point for
  users to share the episode.

## Product Requirements

The custom player should keep the performance and no-iframe advantages without
regressing the episode transcript and share workflow.

1. Speaker labels must render for diarized transcripts.
   The custom-player transcript endpoint must preserve public, sanitized speaker
   labels for speaker names allowed by the episode's visible contributors.
   The rendered transcript should group consecutive cues by speaker and print
   the speaker label once at the start of a speaker run.

2. Transcript timestamps must be visually de-emphasized.
   For speaker-labelled transcripts, do not show an exact timestamp beside every
   cue. Show a muted time anchor only at a speaker-run boundary, or use an
   equivalently sparse treatment that still lets users seek by clicking text.
   Continuation lines in the same speaker run should read like prose/dialogue,
   not like a log table.

3. Transcript should behave like an attached tab/panel header, not a standalone
   button.
   The collapsed `Transcript` affordance should read as the header of the
   transcript region beneath the player. Avoid the current full-width divider
   immediately under the player; instead use a shorter separator aligned with
   the episode-detail content grid, running from the visual bottom of the
   episode number/cover column toward the right column. The transcript header
   should sit above or on this panel region so opening it feels like revealing
   content, not pressing an unrelated button.

4. Transcript loading must have a visible progress state.
   When the transcript panel is opened and the lazy cue request is still in
   flight, show a small spinner or equivalent busy indicator next to the loading
   state. The open control/panel should expose appropriate busy semantics
   (`aria-busy` or an equivalent status region) without moving layout when the
   cues arrive.

5. Opening and closing the transcript panel should feel attached and responsive.
   Use a restrained spring/easing animation for panel reveal/collapse: the
   header/chevron and panel body should move as one component, with no content
   overlap and no layout jump. Respect `prefers-reduced-motion` by disabling or
   simplifying the animation.

6. The transcript panel should match the quality bar of staging.
   Keep the light, readable panel treatment, dark body text, clear speaker
   labels, restrained active-cue highlighting, transcript search, previous/next
   match controls, and follow-current-cue behavior. Verify the panel at desktop
   and mobile widths.

7. The ambiguous `Tab cues` control should not remain as a primary toolbar
   button.
   Either remove it from the visible toolbar, move it into a keyboard/help
   preference surface, or relabel it with understandable copy such as
   `Keyboard cues`. If the feature remains, keep its accessible name and
   persisted preference correct.

8. Django Chat should expose one user-facing share entry point.
   Remove or suppress the custom player's in-transport share button for Django
   Chat. The site-level share modal is the canonical share UI because it handles
   social targets, copy, Mastodon, the no-JS fallback, and timestamped links.

9. Timestamped sharing must keep working through the single share UI.
   Opening the Django Chat share modal after playback or seeking must prefill
   `Start at`, set the time input, and update every generated URL to include the
   correct `?t=<seconds>` value. The copied URL and all social/email share links
   must use the same timestamped URL.

## Implementation Scope

This is a cross-repo player polish slice.

- Generic custom-player behavior belongs upstream in `../django-cast` first:
  sparse transcript timestamp rendering, speaker-run grouping regression tests,
  loading state, cue keyboard preference UI, animation hooks, and an opt-out for
  the built-in transport share control.
- Django Chat owns project-specific presentation and integration:
  `django_chat/static/django_chat/css/site.css`,
  `django_chat/templates/cast/django_chat/audio.html`,
  `django_chat/templates/cast/django_chat/episode.html`,
  `django_chat/static/django_chat/js/share-modal.js`, and the browser tests
  under `django_chat/core/tests/test_browser_js.py`.
- Do not edit `.venv/` package files or collected `staticfiles/` output.
  Implement upstream changes in `../django-cast`, then bump the pinned
  `django-cast` rev in this repo with `uv sync`.
- The current worktree already bumps `django-cast` from `e23a288...` to
  `66961f...`. That upstream range adds transcript endpoint caching, constant
  toggle width, and always-collapsed panels, and the current pin already
  includes speaker-heading rendering when cue data contains public speaker
  labels. It does not complete this spec.
- If the final implementation needs no upstream code change, document why in
  the PR/commit notes; otherwise keep the upstream change and Django Chat pin
  bump as separate logical commits.

## Implementation Plan

Follow these steps in order. Do not skip the data audit: otherwise an
implementation can accidentally polish around a fixture problem while still
leaving the real staging behavior unproven.

1. Audit transcript speaker data and sanitization.
   Confirm whether the local `django-tasks-jake-howard` transcript artifact
   actually contains speaker labels before sanitization, whether matching
   visible contributors are assigned, and why
   `/api/audios/1/player-transcript/?post_id=4` returns `speaker: ""` locally
   while staging's Podlove endpoint returns names. If local data is stale or
   incomplete, fix the representative fixture/import state or add a focused
   browser-test fixture with contributor-approved speaker labels. If the custom
   endpoint is dropping valid labels, fix the endpoint upstream in django-cast.
   The three-speaker `django-tasks-jake-howard` dev-server state noted in
   `../django-cast/backlog/2026-06-03-custom-audio-player-follow-ups.md` was
   manually injected into a dev database and is not committed code, so do not
   treat that named episode as reproducible until its data source has been
   re-seeded or replaced by a committed fixture.

2. Preserve speaker labels in the custom transcript endpoint.
   Add or extend upstream django-cast tests so `AudioPlayerTranscriptView`
   returns cues with `speaker: "<allowed contributor display name>"` after
   applying public speaker mapping and sanitization. Also assert that a
   non-contributor speaker is stripped, preserving the existing privacy
   contract.

3. De-emphasize timestamps in speaker-labelled transcripts.
   At django-cast pin `66961f...`, the transcript element already inserts
   `.cast-transcript__speaker` headings when a cue carries a new non-empty
   speaker, and empty-speaker cues already reset the speaker run. Verify that
   behavior with tests, but do not reimplement it. The remaining rendering work
   is timestamp treatment. In labelled mode:
   - detect labelled mode with `cues.some(cue => cue.speaker.trim())`;
   - show a muted time anchor only on speaker-run starts and empty-speaker
     anchored cues;
   - hide or visually de-emphasize continuation timestamps without removing
     click-to-seek behavior or useful accessible labels;
   - keep search highlighting, current-cue highlighting, follow scrolling,
     speaker headings, empty-speaker run resets, and cue click-to-seek working
     per cue.
   In unlabelled mode, keep the current per-cue timestamp behavior.

4. Add transcript loading feedback.
   Replace the plain `Loading transcript...` state with a compact spinner plus
   status text. The panel body should expose a busy state while the lazy request
   is in flight, then swap to cues without changing the toolbar height or
   shifting surrounding content.

5. Rework the transcript toggle into an attached panel header.
   The control may remain a semantic `<button>` or use proper tab/disclosure
   semantics for accessibility, but it must not look like a large standalone
   pill button. Style it as the header for the transcript panel beneath the
   player. Remove the broad divider feel below the player by replacing it with
   a shorter separator aligned to the episode detail grid and cover/sidebar
   rhythm. Verify the separator on desktop and at the mobile stack breakpoint.

6. Add restrained reveal/collapse motion.
   Use a spring-like easing for opening and closing the transcript panel. The
   header/chevron and body should feel connected, avoid content overlap, and
   avoid layout jumps. Disable or simplify the effect under
   `prefers-reduced-motion: reduce`.

7. Demote the cue-tab preference.
   The text `Tab cues` must not appear as a primary toolbar button. Keep the
   accessibility preference available as an icon/secondary control with
   `aria-label="Keyboard-navigable cues"` and a clear tooltip/title, or move it
   into a keyboard/help/preferences surface. Preserve the
   `cast-transcript-tabbable` storage behavior if the feature remains.

8. Remove the duplicate player share entry point for Django Chat.
   Add a generic django-cast opt-out for the transport share button, for example
   a host attribute such as `data-share="none"` or equivalent payload/template
   flag. Use that opt-out from Django Chat so the sidebar rail share item is the
   only visible share entry point. Do not hide the button with fragile global
   CSS if an explicit component option can be added.

9. Keep current-time sharing on the site modal.
   Preserve `cast-audio-player.getShareState()` and the existing
   `share-modal.js` prefill behavior. After seeking or playing, opening the
   Django Chat share modal must set `Start at`, render the formatted time, and
   propagate the timestamped URL to copy, Twitter/X, Facebook, LinkedIn,
   Mastodon, and email links.

10. Update docs that describe the active player.
    Once implementation lands, update stale Podlove-specific host-review or
    staging-differences text if the custom player is now the review target.
    Check `docs/host-review-guide.md`, `docs/staging-differences.md`,
    `docs/css-architecture.md`, `README.md`, and
    `docs/implementation-status.md`. Do not create a changelog casually; if no
    release-note convention applies, say so in the handoff.

## Implementation Notes

- The custom player backend in django-cast already normalizes cues with a
  `speaker` field after applying the public speaker mapping and sanitization.
  The implementation should determine why the local
  `player-transcript` endpoint returns blank speaker fields for this episode
  while the staging Podlove endpoint returns names.
- If the fix belongs in django-cast's custom player source, prefer an upstream
  django-cast change plus a deliberate `django-cast` pin bump in this repo.
  If Django Chat needs project-specific presentation only, keep the override
  local and small.
- The transcript detail page already contains script-style grouping helpers in
  `django_chat/templates/cast/django_chat/transcript.html`; use that behavior
  as the local reference for grouping by speaker.
- Django's template settings include `django_chat/templates` before app
  templates, so Django Chat can override `cast/audio/_custom_player.html` if a
  local template hook is needed. Prefer an explicit upstream extension point
  over a template override when the behavior is generally useful.
- The existing browser-test helper `_create_generated_transcript()` in
  `django_chat/core/tests/test_browser_js.py` creates speaker-labelled cues.
  Reuse or extend it together with matching visible `EpisodeContributor` records
  so browser tests prove contributor-approved labelled rendering without relying
  on mutable local/staging data. A test that creates `"Host"` cues but no
  matching contributor is not sufficient because sanitization should strip that
  label.

## Verification Plan

Run these checks before calling the implementation complete:

```bash
just test
just test-browser
uv run prek run --files \
  pyproject.toml uv.lock \
  django_chat/static/django_chat/css/site.css \
  django_chat/templates/cast/django_chat/audio.html \
  django_chat/templates/cast/django_chat/episode.html \
  django_chat/static/django_chat/js/share-modal.js \
  django_chat/core/tests/test_browser_js.py \
  docs/custom-player-transcript-share-spec.md \
  docs/implementation-status.md
```

Also run a Playwright/manual browser pass on
`/episodes/django-tasks-jake-howard/` with the dev server:

- desktop viewport around 1240 x 900;
- a mobile/narrow viewport at or below the episode-detail stack breakpoint;
- transcript closed on first load;
- open transcript and observe spinner while the lazy request is in flight;
- verify visible speaker headings and sparse timestamps using either committed
  test fixture data or a documented re-seeded `django-tasks-jake-howard`
  transcript/contributor state;
- search transcript text and navigate matches;
- play or seek to 21 seconds, open the site share modal, and verify `?t=21` in
  the URL field and generated share links;
- verify only one visible Share affordance on the page;
- verify reduced-motion mode removes or simplifies the reveal animation.

## Acceptance Criteria

- A repository-backed browser test fixture creates a transcript with matching
  visible contributors and shows visible speaker labels in the custom transcript
  panel.
- If `/episodes/django-tasks-jake-howard/` is used for manual parity review, its
  three-speaker transcript/contributor data source is documented and re-seeded
  first; then the custom transcript panel shows `Carlton Gibson`,
  `Will Vincent`, and `Jake Howard`.
- The first visible transcript lines no longer show a timestamp next to every
  cue.
- The collapsed `Transcript` affordance reads as a panel/tab header attached to
  the transcript region, and the old full-width horizontal rule directly below
  the player is replaced by a shorter grid-aligned separator.
- Opening the transcript shows a spinner or equivalent busy indicator while the
  lazy transcript request is in flight, then swaps to loaded cues without
  layout shift.
- The transcript reveal/collapse uses a restrained spring-style motion and
  honors `prefers-reduced-motion`.
- The text `Tab cues` is not visible as a primary transcript toolbar button.
- Exactly one user-facing episode share button is visible on the episode page.
- After seeking to 21 seconds and opening the site share modal, the URL field
  contains `?t=21`, and at least one social share href uses that same URL.
- Regression coverage includes the custom transcript endpoint preserving an
  allowed speaker label, the custom transcript panel rendering speaker headings,
  absence/suppression of the in-player share button, and timestamped site-share
  behavior.
- Relevant docs are updated or explicitly marked not applicable in the handoff.
