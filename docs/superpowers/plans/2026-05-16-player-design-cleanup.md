# Player design cleanup implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the dark-green Podlove tab panel with a light leaf-tint panel that has rounded corners, dark text, share-pill-styled Follow/Stop buttons, and a share-modal-style close (×); remove the redundant in-player share tab; align the click-to-load facade.

**Architecture:** All visual styling for the tab panel ships as a single `<style>` block at the top of `player_template.html` scoped via a `dc-player-tabs` marker class. The share tab is removed from the player template in three places; the click-to-load facade in `audio.html` drops one of its six placeholder dots to match. An existing template-meta test is updated to assert the share tab is absent. The dark-green controls strip and Podlove theme tokens stay untouched.

**Tech Stack:** Django templates, vanilla CSS (no preprocessor), pytest + Django test client. Podlove Web Player v5 renders the template in Light DOM (existing rules in `site.css:2450–3072` already cascade through).

**Spec:** `docs/superpowers/specs/2026-05-16-player-design-cleanup-design.md`

---

## Task 1: Fail the test for share-tab removal

**Files:**
- Modify: `django_chat/core/tests/test_template_meta.py:272`

- [ ] **Step 1: Flip the existing share-trigger assertion**

Open `django_chat/core/tests/test_template_meta.py`. The current test asserts the share trigger is **present** (line 272). Replace that assertion so the test now asserts the trigger is **absent**, and also asserts the tab body is absent:

```python
    assert "<tab-transcripts></tab-transcripts>" in body
    assert '<tab-trigger tab="share">' not in body
    assert "<tab-share></tab-share>" not in body
    assert 'style="max-height:420px;"' in body
```

- [ ] **Step 2: Run the test and verify it FAILS**

```bash
just test django_chat/core/tests/test_template_meta.py::test_podlove_player_template_endpoint_renders_compact_template -v
```

Expected: FAIL — assertion `'<tab-trigger tab="share">' not in body` is False because the share trigger is still in `player_template.html`.

- [ ] **Step 3: Do NOT commit yet**

The failing test is the entry point of the change in Task 2. Leave the working tree dirty so Task 2's commit captures the test + production-code change together.

---

## Task 2: Remove the share tab and align the facade

**Files:**
- Modify: `django_chat/templates/cast/django_chat/player_template.html` (lines 29–31, 55–57, 78–80)
- Modify: `django_chat/templates/cast/django_chat/audio.html` (lines 33–40)

- [ ] **Step 1: Remove the desktop share tab trigger**

In `player_template.html`, delete the desktop share trigger (lines 29–31):

```html
          <tab-trigger tab="share">
            <icon type="share"></icon>
          </tab-trigger>
```

…and remove the trailing class `mr-4` from the preceding `<tab-trigger tab="playlist">` if it now sits in the last position. After the edit, the last desktop trigger in that row reads:

```html
          <tab-trigger tab="playlist">
            <icon type="playlist"></icon>
          </tab-trigger>
```

- [ ] **Step 2: Remove the mobile share tab trigger**

In `player_template.html`, delete the mobile share trigger (lines 55–57):

```html
          <tab-trigger tab="share">
            <icon type="share"></icon>
          </tab-trigger>
```

The preceding mobile `<tab-trigger tab="playlist">` keeps its existing classes (no `mr-4` on the mobile row).

- [ ] **Step 3: Remove the tab body**

In `player_template.html`, delete the share tab body (lines 78–80):

```html
    <tab name="share">
      <tab-share></tab-share>
    </tab>
```

- [ ] **Step 4: Drop one facade dot in `audio.html`**

In `audio.html`, lines 33–40, the click-to-load facade currently renders six `<span></span>` children of `.podlove-facade-tabs`. Delete one of them so it reads:

```html
          <span class="podlove-facade-tabs" aria-hidden="true">
            <span></span>
            <span></span>
            <span></span>
            <span></span>
            <span></span>
          </span>
```

- [ ] **Step 5: Run the template-meta test and verify it PASSES**

```bash
just test django_chat/core/tests/test_template_meta.py::test_podlove_player_template_endpoint_renders_compact_template -v
```

Expected: PASS.

- [ ] **Step 6: Run the full test suite to confirm no regressions**

```bash
just test
```

Expected: all green.

- [ ] **Step 7: Run the configured hook runner**

Check `prek.toml` / `.pre-commit-config.yaml` to determine which tool is configured. Then run it on the changed files:

```bash
prek run --files django_chat/templates/cast/django_chat/player_template.html django_chat/templates/cast/django_chat/audio.html django_chat/core/tests/test_template_meta.py
```

If `prek` is not the configured hook runner, fall back to `pre-commit run --files <same list>`.

Expected: hooks pass.

- [ ] **Step 8: Commit**

```bash
git add django_chat/templates/cast/django_chat/player_template.html \
        django_chat/templates/cast/django_chat/audio.html \
        django_chat/core/tests/test_template_meta.py
git commit -m "Remove in-player share tab and align facade"
```

---

## Task 3: Restyle the tab panel wrapper

**Files:**
- Modify: `django_chat/templates/cast/django_chat/player_template.html` (line 1 — add a `<style>` block as first child inside `<root>`; line 62 — modify the wrapper div)

This task ships the visible win: light panel, rounded corners, dark text. Inner-element restyling (close ×, Follow/Stop buttons, followed-line highlight) is Task 4.

- [ ] **Step 1: Modify the tab panel wrapper**

In `player_template.html` line 62, change:

```html
  <div class="w-full relative overflow-auto" style="max-height:420px;">
```

to:

```html
  <div class="dc-player-tabs relative overflow-auto" style="max-height:420px;">
```

Notes:
- `w-full` is dropped so the upcoming horizontal margin does not produce a `100% + 24px` overflow.
- `dc-player-tabs` is the new marker class; the style block targets it.
- `relative overflow-auto` and the inline `max-height:420px;` are structural and stay.

- [ ] **Step 2: Add the `<style>` block as the first child inside `<root>`**

In `player_template.html`, immediately after the opening `<root …>` tag (after line 1) and before the controls-strip `<div class="p-4 flex flex-col">`, insert:

```html
  <style>
    /* Tab panel wrapper — replaces the dark-green chrome with a leaf-tint
       card. Selectors are prefixed with [data-test="player--m"] so rules
       only match inside the player; the player's <root> always carries
       data-test="player--m" (see line 1). */
    [data-test="player--m"] .dc-player-tabs {
      margin: 12px;
      padding: 18px 20px;
      background: #e6f0dc;
      color: #0d0d0d;
      border: 1px solid #cdddc1;
      border-radius: 16px;
      line-height: 1.55;
    }

    [data-test="player--m"] .dc-player-tabs a {
      color: #14513a;
      text-decoration-thickness: 0.08em;
      text-underline-offset: 0.18em;
    }

    /* Speaker / timestamp eyebrows render via Podlove's own typography;
       keep them muted instead of inheriting the new dark body colour. */
    [data-test="player--m"] .dc-player-tabs time,
    [data-test="player--m"] .dc-player-tabs .speaker,
    [data-test="player--m"] .dc-player-tabs [class*="timestamp"] {
      color: #5f635d;
    }
  </style>
```

- [ ] **Step 3: Start the dev server**

```bash
just manage runserver
```

Leave it running for the rest of this task.

- [ ] **Step 4: Open the player in a browser and verify the wrapper**

Open an episode that has a transcript (e.g. http://localhost:8000/episodes/django-tasks-jake-howard/ via the staging sample). Click the play facade to load the player, then open the transcripts tab.

Check, against the spec table (`docs/superpowers/specs/2026-05-16-player-design-cleanup-design.md:51–59`):

- Panel background `#e6f0dc`.
- Panel border `1px solid #cdddc1`.
- Panel radius `16px`.
- 12px margin between the dark-green controls strip and the new panel (no horizontal overflow — the panel is fully inside the player width).
- Body transcript text is dark `#0d0d0d`, readable on the new background.
- Speaker / timestamp eyebrow rows stay muted grey, not dark.
- Hover state on any in-panel links uses `#14513a`.

If body text is still white (Podlove's `alt` token applied via inline style), confirm in devtools whether an inline `style="color: #fff"` is being set on a Podlove inner element; if so, note the selector — Task 4 will override it. Otherwise carry on.

- [ ] **Step 5: Check shownotes, chapters, files, playlist**

Cycle through the remaining tabs in the player. Every tab should now render inside the same leaf-tint card. The inner list/text content keeps its native structure; only colors and chrome change.

- [ ] **Step 6: Check mobile viewport**

Resize the browser to ≤ 760px (DevTools device toolbar). The tab panel should still have the new chrome and stay within the player width.

- [ ] **Step 7: Check the embed page**

Open http://localhost:8000/episodes/django-tasks-jake-howard/embed/ (path mirrors `django_chat_episode_embed`). The same chrome should apply because `episode_embed.html` includes the same player template.

- [ ] **Step 8: Confirm the test still passes**

```bash
just test django_chat/core/tests/test_template_meta.py::test_podlove_player_template_endpoint_renders_compact_template -v
```

Expected: PASS.

- [ ] **Step 9: Run hooks**

```bash
prek run --files django_chat/templates/cast/django_chat/player_template.html
```

Expected: PASS.

- [ ] **Step 10: Commit**

```bash
git add django_chat/templates/cast/django_chat/player_template.html
git commit -m "Restyle player tab panel with leaf-tint card chrome"
```

---

## Task 4: Restyle the close (×) button, Follow / Stop buttons, and followed-line highlight

**Files:**
- Modify: `django_chat/templates/cast/django_chat/player_template.html` (extend the `<style>` block from Task 3)

The three remaining elements are rendered by Podlove using class names that are not known from static analysis of the minified `embed.5.js`. This task discovers the selectors in devtools and then applies the rules.

- [ ] **Step 1: Make sure the dev server is running and open the transcripts tab**

If the server stopped, restart with `just manage runserver` and reopen http://localhost:8000/episodes/django-tasks-jake-howard/ → load player → open transcripts.

- [ ] **Step 2: Capture the close (×) button selector**

In devtools Elements panel, inspect the small × that closes / collapses the open tab.

Record:

- Its tag and class list (e.g. `<button class="podlove-...">`).
- Whether it lives inside the `dc-player-tabs` wrapper or outside it (siblings of the tab body).
- Whether it sits inside a Shadow DOM root. (If it does, the rest of this step's CSS won't reach it — note that in the commit message and skip styling it; the wrapper is already the readability win.)

Write the captured selector as a comment in the `<style>` block, then append a rule:

```css
/* Close (×): captured via devtools <date> — adjust selector below to
   match Podlove's actual element. */
[data-test="player--m"] .dc-player-tabs <captured-selector> {
  width: 38px;
  height: 38px;
  border-radius: 999px;
  background: transparent;
  border: 0;
  color: #14513a;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition: background-color 0.15s ease, color 0.15s ease;
}
[data-test="player--m"] .dc-player-tabs <captured-selector>:hover {
  background: rgb(77 165 83 / 0.12);
}
[data-test="player--m"] .dc-player-tabs <captured-selector>:focus-visible {
  outline: none;
  background: rgb(77 165 83 / 0.12);
  box-shadow: 0 0 0 3px rgb(77 165 83 / 0.18);
}
```

Substitute `<captured-selector>` with the actual selector you recorded. Save and reload the page. The button should now be a circular hit area with dark-green ink, tinted hover, and a keyboard-visible focus ring.

- [ ] **Step 3: Capture the Follow / Stop button selectors**

In devtools, click into the transcripts tab and locate the "Follow text" button. Inspect it; record its tag and class list. Do the same for "Stop text" / "Stop following" (it may share the same class as Follow text with an `aria-pressed` attribute, or it may be a separate class — check both states by clicking the button).

Append rules to the `<style>` block:

```css
/* Follow / Stop buttons — share-pill styling. */
[data-test="player--m"] .dc-player-tabs <captured-selector> {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-height: 36px;
  padding: 0 14px;
  border: 1px solid #14513a;
  border-radius: 999px;
  color: #14513a;
  background: transparent;
  font: inherit;
  font-size: 0.88rem;
  font-weight: 600;
  cursor: pointer;
  transition: background-color 0.15s ease, border-color 0.15s ease, color 0.15s ease;
}
[data-test="player--m"] .dc-player-tabs <captured-selector>:hover {
  background: rgb(77 165 83 / 0.10);
  border-color: #4da553;
}
[data-test="player--m"] .dc-player-tabs <captured-selector>:focus-visible {
  outline: none;
  background: rgb(77 165 83 / 0.10);
  border-color: #4da553;
  box-shadow: 0 0 0 3px rgb(77 165 83 / 0.18);
}
/* Active / pressed state (Stop following). */
[data-test="player--m"] .dc-player-tabs <captured-selector>[aria-pressed="true"],
[data-test="player--m"] .dc-player-tabs <captured-selector>.is-active {
  background: rgb(77 165 83 / 0.10);
}
```

Substitute `<captured-selector>` with the actual selector(s) you recorded. If Follow/Stop are two separate elements, repeat each rule for each selector. Save and reload — buttons should now look like share pills.

- [ ] **Step 4: Capture the followed-line highlight selector**

Click "Follow text" to start auto-scrolling, then play the audio for ~10 seconds. Inspect the transcript line that's currently highlighted as the audio plays. Record its tag and class list. Also inspect a non-active line to confirm the difference.

If the active line uses inline `style="color: …"`, that will override our CSS; in that case use `!important` on `color` and `font-weight` in the rule below. Otherwise omit `!important`.

Append the rule:

```css
/* Currently-followed transcript line. */
[data-test="player--m"] .dc-player-tabs <captured-active-line-selector> {
  color: #14513a;
  font-weight: 600;
}
```

Substitute `<captured-active-line-selector>` with the actual selector. If Podlove only marks the active line via an attribute (e.g. `[data-active="true"]`), use that attribute as the selector.

- [ ] **Step 5: Verify each restyled element**

Reload the episode page, open transcripts, and walk through:

- × button: circular, dark-green ink, hover tint, keyboard focus ring (tab into the button via keyboard).
- Follow text / Stop following: pill geometry, dark-green border, hover + active states feel like the `.share-pill` styling on the episode page.
- Followed line: switches to `#14513a` + weight 600 as audio plays; inactive lines stay dark `#0d0d0d`.

If any of these did not change after the rule was applied, the captured selector did not match — revisit devtools, refine the selector, and retest.

- [ ] **Step 6: Check the embed page**

Open http://localhost:8000/episodes/django-tasks-jake-howard/embed/ and confirm the same three elements look correct inside the embed iframe.

- [ ] **Step 7: Final regression sweep**

```bash
just test
prek run --all-files
```

Expected: all green.

- [ ] **Step 8: Commit**

```bash
git add django_chat/templates/cast/django_chat/player_template.html
git commit -m "Restyle player tab panel close, follow buttons, and active line"
```

If the followed-line selector turned out to be inside a Shadow DOM and could not be reached by CSS, omit that rule from the commit and add a one-line code comment explaining the limitation. The other two pieces still ship.

---

## Self-review checklist (for the implementer)

After Task 4, before considering the work done, review the spec line-by-line against what shipped:

- [ ] Scope items 1–3 in `docs/superpowers/specs/2026-05-16-player-design-cleanup-design.md:28–34` all done.
- [ ] All values in the spec's token table (`spec:51–59`) appear in the `<style>` block.
- [ ] Files-touched list in `spec:113–122` matches the actual diff (`git diff --stat HEAD~3`).
- [ ] Files-not-touched in `spec:124–134` are still unmodified.
- [ ] Out-of-scope items in `spec:136–148` were not touched (no controls-strip changes, no token changes, no `share-modal.js`/`podlove-loader.js` changes).
- [ ] Verification checklist in `spec:152–172` passes.

If any item is unchecked, fix or document it before declaring done.
