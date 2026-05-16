# Player design cleanup

Date: 2026-05-16

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
- Drop the in-player "share" tab.
- Prefill the site share modal's "Start at" input with the player's current
  time when the modal opens (toggle stays off).

Out of scope:

- Restyling the dark-green controls strip (play button row, tab icon row).
  The strip keeps today's tokens (`brand`, `brandDark`, `brandDarkest`).
- Restyling the outer iframe wrapper (no card around the whole player).
- Forking or patching Podlove Web Player internals.

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

1. Add a `<style>` block at the top of the template. Every selector in it
   is prefixed with `[data-test="player--m"]` so the rules only match inside
   the player's `<root>`. (The block is global like any `<style>` tag; the
   selector prefix is what prevents collisions with the surrounding page.)
   This block holds:
   - Tab panel wrapper rules (bg, border, radius, padding, color)
   - Close (×) restyle
   - Follow / Stop button restyle
   - Followed-line highlight (`color: #14513a; font-weight: 600;`)
2. Remove the share tab in three places:
   - `tab-trigger tab="share"` in the desktop tab bar (lines 29–31)
   - `tab-trigger tab="share"` in the mobile tab bar (lines 55–57)
   - `<tab name="share"><tab-share></tab-share></tab>` (lines 78–80)
3. Apply inline style to the existing tab panel wrapper
   (`<div class="w-full relative overflow-auto" style="max-height:420px;">`,
   line 62) for the bg / border / radius / margin. (Inline matches the
   existing pattern on `<root>` at line 1.)

The scoped `<style>` block penetrates Podlove's tab content because the player
uses Light DOM (existing `site.css:2450–3072` rules already cascade in this
way). See "Risks" for the followed-line caveat.

### Share modal time prefill

`django_chat/static/django_chat/js/share-modal.js`:

In the existing trigger click handler (currently `renderPills();
closeMastodonPrompt(); updateMastodonStatus(); dialog.showModal();`), add a
prefill step before `dialog.showModal()`:

1. Read the latest known player time from a module-level accessor exposed by
   `podlove-loader.js` (e.g. `window.djangoChatPlayerTime?.get?.()`).
2. If it is a finite number `> 0`, format `Math.floor(value)` as `MM:SS` and
   assign to `[data-startat-time].value`.
3. Leave `[data-startat-toggle]` unchanged (its previous state persists).
4. Call `renderPills()` again after the assignment so the URL preview /
   pill hrefs pick up the new value if the toggle happens to be on.

The accessor is populated by a `message` event listener added in
`podlove-loader.js`. The listener:

- Filters messages to those whose `source` is one of the player iframes.
- Inspects `event.data` for a playtime payload. Exact message shape is
  determined during implementation by logging Podlove's emissions for a real
  episode and documenting the matched shape in a code comment.
- Caches the most recent value at module scope; exposes a getter.

If Podlove emits no usable playtime message, the cached value stays unset and
the share modal opens with an empty input (today's behavior). The
implementation comment near the listener mirrors the existing note at
`podlove-loader.js:200–215` documenting which message shapes were tried.

## Files touched

- `django_chat/templates/cast/django_chat/player_template.html` — add scoped
  `<style>` block, remove share tab triggers and tab body, inline-style the
  tab panel wrapper.
- `django_chat/static/django_chat/js/podlove-loader.js` — add a `message`
  listener that caches playtime and exposes a getter.
- `django_chat/static/django_chat/js/share-modal.js` — read the getter on
  dialog open and prefill `[data-startat-time]`.
- `django_chat/core/tests/` — add a test (e.g. `test_player_template.py`)
  asserting that the rendered player template no longer contains
  `tab="share"` or `<tab name="share">`. Uses Django's test client or
  `render_to_string` against the `django_chat_podlove_player_template` URL.

## Files not touched

- `config/settings/base.py` (`CAST_PODLOVE_PLAYER_THEMES`) — controls strip
  keeps its dark-green tokens. Changing them globally would break the strip,
  which is out of scope.
- `episode_embed.html` — receives the new tab panel chrome automatically
  because it includes the same player template.
- `transcript.html` — separate full-page transcript view, unaffected.

## Risks

1. **Followed-line selector** — Podlove names the active transcript line
   with some class (likely `.active` or `.current`). If the line is rendered
   in Shadow DOM, the highlight rule silently no-ops. Mitigation: during
   implementation, inspect transcripts in devtools to confirm the class and
   DOM boundary. If Shadow DOM: ship the rest of the change and open a
   follow-up note. The base panel (light bg, dark text) still ships and is
   the main readability win.

2. **Iframe playtime bridge** — `podlove-loader.js:200–215` already documents
   that parent → player messaging via Podlove's internal Redux action shape
   and via hash propagation both failed. The reverse direction (player →
   parent message events) has not been verified yet. If the player emits no
   usable playtime message in current builds, the prefill is a no-op and the
   modal opens with an empty input (today's behavior). No user-visible
   breakage; the work cost is bounded (~30 lines).

## Out of scope / future

- Restyling the dark-green controls strip.
- Custom theme tokens per tab.
- Receiver-side auto-seek when the page is opened with `?t=` (existing
  `podlove-loader.js` comment block already tracks this).

## Verification

Manual browser pass (dev server, real episode):

- Open transcripts; verify panel bg `#e6f0dc`, 16px radius, 1px `#cdddc1`
  border, ink body text, muted eyebrow, 12px gap from the controls strip.
- Cycle through shownotes / chapters / files / playlist — all share the new
  chrome.
- Share tab absent from both desktop and mobile tab bars.
- Play and scrub audio; the followed transcript line switches to `#14513a`,
  weight 600. If not, capture the actual class in devtools and decide
  ship-with-followup vs fix-now per "Risks".
- Close (×): circular hit area, hover tint, keyboard-visible focus ring.
- Follow text / Stop following: pill geometry, hover and active states feel
  like share-pills.
- Mobile viewport (≤ 760px) — same checks.
- Embed page in iframe — same checks.

Share modal prefill:

- Load page, play for ~30 s, open share modal → "Start at" input shows
  ~`00:30`, toggle off. Toggle on → URL gains `?t=30`. Paste in incognito →
  episode loads (existing `?t=` parser handles this).
- With audio at 0 (or never played), share modal opens with empty input.
- Devtools console clean.

Quality gates:

- `just test` green; new template test asserts share tab is gone.
- Configured hook runner passes.
