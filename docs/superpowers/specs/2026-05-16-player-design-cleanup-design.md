# Player design cleanup

Date: 2026-05-16

> Architecture update, 2026-05-17: the template-side `<style>` /
> `dc-player-tabs` approach described below was superseded after it broke
> Podlove rendering. The shipped implementation keeps
> `player_template.html` visually neutral and injects tab-panel CSS into the
> same-origin Podlove iframe from
> `django_chat/static/django_chat/js/podlove-loader.js`.
>
> Follow-up, 2026-05-18: the neutral template wrapper no longer carries
> `overflow-auto` or `max-height:420px`; Podlove's
> `[data-test="tab-transcripts--results"]` element is the transcript tab's only
> vertical scroller. Non-transcript tab bodies keep a 420px internal panel cap
> through the same iframe CSS injection path.

## Background

The Podlove Web Player is embedded on the episode detail page and the
`episode_embed.html` standalone embed page. Its controls strip and tab panels
(transcript, shownotes, chapters, files, playlist, share) are rendered by
Podlove using `player_template.html` as the outer structure. Color is driven by
the Podlove theme tokens in `CAST_PODLOVE_PLAYER_THEMES` (`config/settings/base.py`).

User-reported design issues:

- Tab panel uses white text on dark green (`brandDarkest: #14513a`). Hard to
  read against the surrounding light page; visually heavy.
- The in-panel close (×) does not match the site's `.share-modal-close`.
- The in-panel "Follow text" / "Stop text" buttons do not match the site's
  `.share-pill`.
- The tab panel frame has square corners; site modals use 14–16px radius.
- The in-player "share" tab duplicates the site share modal, and only the
  modal can produce a timestamped link.

## Scope

In scope:

- Restyle the tab panel chrome (background, border, radius, text color, close
  button, follow buttons) for all tabs.
- Drop the in-player "share" tab; the site share modal becomes the sole
  share entry point.
- Update the click-to-load facade in `audio.html` to reflect five tabs
  instead of six.

Out of scope:

- Restyling the dark-green controls strip (play button row, tab icon row).
  The strip keeps today's tokens (`brand`, `brandDark`, `brandDarkest`).
- Restyling the outer iframe wrapper (no card around the whole player).
- Forking or patching Podlove Web Player internals.
- Prefilling the share modal's "Start at" input with the player's current
  time. A spike against the Podlove v5 bundle confirmed there is no
  parent-side message exposing playtime; making one work would require
  injecting a script into the iframe to bridge Podlove's internal Redux
  store, switching to a no-iframe embed mode, or forking `embed.5.js`.
  Tracked as a separate follow-up spec.

## Design

### Tab panel chrome

Apply a "leaf tint" panel that matches the embed-placeholder family.

Tokens (CSS values, not Podlove tokens):

| Role | Value |
| --- | --- |
| Panel background | `#e6f0dc` |
| Panel border | `1px solid #cdddc1` |
| Panel radius | `16px` |
| Panel inset from controls strip | `margin: 12px` |
| Body text | `#0d0d0d` (ink) |
| Eyebrow / speaker / timestamp | `#5f635d` (muted) |
| Currently-followed transcript line | `#14513a`, font-weight 600 |
| Close (×) | 38px circle, `color: #14513a`, hover bg `rgb(77 165 83 / 0.12)`, focus ring `0 0 0 3px rgb(77 165 83 / 0.18)` |
| Follow / Stop buttons | pill (`border-radius: 999px`), 1px `#14513a` border, transparent bg, `color: #14513a`, font-weight 600, min-height 36px. Hover: bg `rgb(77 165 83 / 0.10)`, border `#4da553`. Active/pressed (e.g. "Stop following"): bg `rgb(77 165 83 / 0.10)` |

The same wrapper rules apply to every tab (transcripts, shownotes, chapters,
files, playlist). The inner list/text content of each tab keeps its existing
structure; only colors and the button/close affordances are restyled.

### Player template

`django_chat/templates/cast/django_chat/player_template.html`:

1. Add a `<style>` block as the first child **inside** `<root>` (Podlove v5
   templates must have a single top-level `<root>` node — keeping `<style>`
   as a sibling before `<root>` would risk breaking the template parser
   per <https://docs.podlove.org/podlove-web-player/v5/templating/components/root/>).
   Every selector inside the block is prefixed with `[data-test="player--m"]`
   so rules only match inside the player. **All visual styling for the tab
   panel lives in this block** — bg, border, radius, padding, color,
   close (×), Follow / Stop buttons, followed-line highlight. The wrapper
   div itself gets only a structural class hook (see step 3); inline styles
   on the wrapper stay limited to structural concerns only.
2. Remove the share tab in three places:
   - `tab-trigger tab="share"` in the desktop tab bar (lines 29–31)
   - `tab-trigger tab="share"` in the mobile tab bar (lines 55–57)
   - `<tab name="share"><tab-share></tab-share></tab>` (lines 78–80)
3. Modify the existing tab panel wrapper
   (`<div class="w-full relative overflow-auto" style="max-height:420px;">`,
   line 62):
   - **Drop `w-full`** from the class list. With `width: 100%` plus the
     12px horizontal margin we're about to apply, the box would be
     `100% + 24px` wide and overflow horizontally. Letting it default to
     `width: auto` makes the available width shrink to fit the margins.
   - Keep `relative overflow-auto` and the inline `max-height:420px;`
     (purely structural).
   - Add a marker class (e.g. `class="dc-player-tabs"`) so the scoped
     `<style>` block in step 1 can target the wrapper without relying on
     the existing Tailwind utility classes.
   - All visual properties (background, border, border-radius, padding,
     margin, color) are applied to that marker class in the `<style>`
     block, not inline.

The selector-prefixed `<style>` block penetrates Podlove's tab content
because the player uses Light DOM (existing `site.css:2450–3072` rules
already cascade in this way). See "Risks" for the followed-line caveat.

### Click-to-load facade

`django_chat/templates/cast/django_chat/audio.html`:

Drop one of the six `<span>` placeholder dots inside `.podlove-facade-tabs`
(lines 33–40) so the facade renders five dots matching the new tab count
(shownotes, chapters, transcripts, files, playlist).

## Files touched

- `django_chat/templates/cast/django_chat/player_template.html` — add
  `<style>` block as first child inside `<root>`, remove share tab triggers
  and tab body, drop `w-full` from the tab panel wrapper, add a
  `dc-player-tabs` marker class, keep the existing inline `max-height`.
- `django_chat/templates/cast/django_chat/audio.html` — drop one of the six
  facade tab placeholder dots so the click-to-load facade matches the new
  five-tab reality.
- `django_chat/core/tests/test_template_meta.py` — update the existing
  player template assertions (around line 272): replace
  `assert '<tab-trigger tab="share">' in body` with an assertion that the
  share trigger is absent. Optionally add an assertion that the facade in
  `audio.html` renders five `.podlove-facade-tabs > span` children.

## Files not touched

- `config/settings/base.py` (`CAST_PODLOVE_PLAYER_THEMES`) — controls strip
  keeps its dark-green tokens. Changing them globally would break the strip,
  which is out of scope.
- `episode_embed.html` — receives the new tab panel chrome automatically
  because it includes the same player template.
- `transcript.html` — separate full-page transcript view, unaffected.
- `django_chat/static/django_chat/js/share-modal.js`,
  `django_chat/static/django_chat/js/podlove-loader.js` — the time-prefill
  bridge is descoped (see Scope).

## Risks

**Followed-line selector** — Podlove names the active transcript line with
some class (likely `.active` or `.current`). If the line is rendered in
Shadow DOM, the highlight rule silently no-ops. Mitigation: during
implementation, inspect transcripts in devtools to confirm the class and
DOM boundary. If Shadow DOM: ship the rest of the change and open a
follow-up note. The base panel (light bg, dark text) still ships and is the
main readability win.

## Out of scope / future

- Restyling the dark-green controls strip.
- Custom theme tokens per tab.
- Receiver-side auto-seek when the page is opened with `?t=` (existing
  `podlove-loader.js:200–215` comment block already tracks this).
- Share-modal time prefill — separate spec; requires either an in-iframe
  script bridge to Podlove's Redux store, switching off iframe embedding,
  or a patched `embed.5.js`. None fit the scope of this slice.

## Verification

Manual browser pass (dev server, real episode):

- Open transcripts; verify panel bg `#e6f0dc`, 16px radius, 1px `#cdddc1`
  border, ink body text, muted eyebrow, 12px gap from the controls strip.
- Cycle through shownotes / chapters / files / playlist — all share the new
  chrome.
- Share tab absent from both desktop and mobile tab bars.
- Click-to-load facade shows five tab dots (not six) before the player loads.
- Play and scrub audio; the followed transcript line switches to `#14513a`,
  weight 600. If not, capture the actual class in devtools and decide
  ship-with-followup vs fix-now per "Risks".
- Close (×): circular hit area, hover tint, keyboard-visible focus ring.
- Follow text / Stop following: pill geometry, hover and active states feel
  like share-pills.
- Mobile viewport (≤ 760px) — same checks.
- Embed page in iframe — same checks.

Quality gates:

- `just test` green; updated template test asserts share tab is absent.
- Configured hook runner passes.
