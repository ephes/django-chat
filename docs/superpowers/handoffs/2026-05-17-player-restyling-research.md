# Research handoff — Podlove Web Player v5 tab-panel restyling

> **Paste this prompt to a fresh agent session (Claude Code, Codex, or similar) for an independent research pass. Do not implement; only research and recommend.**

---

## Your role

You are a research agent. Read the codebase, the Podlove Web Player v5 docs, and any other public sources you can reach, then recommend a path forward. Do **not** modify code. End with a written recommendation only.

## Background — project

Repo: `/Users/jochen/projects/django-chat`. Django + Wagtail + django-cast podcast site for "Django Chat". The site is not yet live — there is no production cache or audience to break. The Podlove Web Player v5 is embedded on every episode page via django-cast.

The user reported these design issues with the player's expanded tab panels (transcript, shownotes, chapters, files, playlist):

1. The × close button inside the tab panel doesn't match the site's `.share-modal-close` (see `django_chat/static/django_chat/css/site.css:3234-3258`).
2. White-on-dark-green transcript text is hard to read. The user wants **dark text on a light-green background**, similar to the embed-placeholder pattern (`django_chat/templates/cast/django_chat/episode_embed.html:38-58` — bg `rgb(77 165 83 / 0.10)`, text `#14513a`). The currently-followed transcript line should also still be distinguishable.
3. The "Follow text" / "Stop text" buttons inside the tab panel don't match the site's `.share-pill` style (`site.css:3266-3296`).
4. The tab panel frame should be rounded like the share/embed modals (`border-radius: 16px`).
5. The same chrome treatment should cover shownotes, chapters, files, playlist tabs (not only transcript).
6. The in-player Share tab is redundant with the site-level share modal. **(Already shipped — see "What's shipped" below.)**

## What's shipped (do not undo)

Commit `bcb2d08` — **"Remove in-player share tab and align facade"**. This:
- Removed the `<tab-trigger tab="share">` from both rows in `player_template.html` and the `<tab name="share">` body.
- Dropped one of the six facade placeholder dots in `audio.html` so the click-to-load preview matches the new five-tab reality.
- Updated `django_chat/core/tests/test_template_meta.py:272` to assert the share tab is absent.

This change is stable and works. The player renders correctly; the share modal already at `django_chat/templates/cast/django_chat/episode.html:58-147` is the single share entry point.

## What's broken / experimental (currently uncommitted; should likely be reverted)

The working tree contains uncommitted edits from a failed visual-restyling pass:

- `config/settings/base.py:279-292` — `CAST_PODLOVE_PLAYER_THEMES` tokens changed (`brandDarkest` → `#e6f0dc`, `alt` → `#0d0d0d`). Did not deliver the desired bg change; see "What we tried" below.
- `django_chat/templates/cast/django_chat/player_template.html` — wrapper div carries an inline `style="background:#e6f0dc;border:1px solid #cdddc1;border-radius:16px;margin:12px;padding:18px 20px;color:#0d0d0d;line-height:1.55;"`. Renders an empty light-green pill when no tab is open (visible artifact below the controls strip).
- `django_chat/core/tests/test_template_meta.py:228-258` — token assertions updated to match the changed token values.

Also still in git history: commit `013cbb0` ("Restyle player tab panel with leaf-tint card chrome") added a `<style>` block as the first child inside `<root>` in `player_template.html`. **This crashed the player entirely** (page rendered with the audio panel area completely empty). The `<style>` block has since been removed in the working tree; the commit itself still sits on `main`.

Assume the user will revert both the experimental commit `013cbb0` and the uncommitted working-tree edits, returning to `bcb2d08` as the clean baseline, **after** the research is done.

## What we tried and what we learned

### Attempt 1 — `<style>` block inside `<root>` in `player_template.html`

```html
<root data-test="player--m" ...>
  <style>
    [data-test="player--m"] .dc-player-tabs { background: #e6f0dc; ... }
    ...
  </style>
  <div class="p-4 ...">…</div>
  …
</root>
```

**Result:** the player vanished entirely on load. Empty `<podlove-player>` element, no rendered iframe content visible.

**Root cause:** The Podlove player bundle (`staticfiles/cast/js/web-player/embed.5.js`) bundles **DOMPurify** (strings `ALLOWED_TAGS` / `FORBID_TAGS` present in the minified bundle). DOMPurify's default `FORBID_TAGS` includes `<style>`. The `<style>` element was stripped from the template before Vue compiled it, and stripping plus whatever happened next produced a render failure for the entire player.

### Attempt 2 — Inline `style="…"` on the tab panel wrapper div

```html
<div class="relative overflow-auto"
     style="max-height:420px;background:#e6f0dc;border:1px solid #cdddc1;border-radius:16px;padding:18px 20px;margin:12px;color:#0d0d0d;">
  <tab name="shownotes">…</tab>
  …
</div>
```

**Result:** The wrapper div renders with the leaf-tint chrome, but:

- The **inner tab panel content** (transcript text, etc.) is still painted by Podlove with its own dark-green background **inside** our wrapper. So instead of a single light panel, we get an empty light-green frame around a dark-green inner box (worse than the original look, and the inner panel is still hard to read).
- When no tab is open, the wrapper still renders the padding + border + bg, producing an empty light-green pill artifact below the controls strip.

### Attempt 3 — Theme token change

`config/settings/base.py` `CAST_PODLOVE_PLAYER_THEMES["django_chat"]["tokens"]`:

- `brandDarkest`: `#14513a` → `#e6f0dc`
- `alt`: `#ffffff` → `#0d0d0d`

**Result:**
- The `alt` change worked — transcript text is now dark (`color: rgb(13, 13, 13)` in the DOM).
- The `brandDarkest` change had no visible effect on the tab panel background. The panel is still painted dark green, just a slightly different shade than before. Net effect: **dark text on dark green — worse than the original**.

### Architectural facts discovered (verified via a Playwright probe — see `/tmp/inspect_player.py`)

These are facts, not guesses. They are the constraints any new approach has to live with.

1. **Podlove Web Player v5 uses Vue 3** inside the player iframe. The mount root is `<div id="app" data-test="player" data-v-app="">`. The `data-v-app` attribute is Vue 3's mount marker.
2. **Template custom elements are replaced by Vue at render time.** `<root>` becomes `<div data-test="player--m">`; `<tab-trigger>`, `<tab-transcripts>`, `<play-button>` etc. all become regular `<div>` / `<button>` after Vue compiles. So CSS selectors targeting those custom element tag names will not match anything in the rendered DOM.
3. **Theme tokens are baked as inline `style="…"` attributes on rendered elements by Vue at runtime — there are NO CSS custom properties.** The probe confirmed: zero `--brand*` custom properties on any element. `getComputedStyle(html).getPropertyValue('--brand')` returns `""`. So `var(--brandDarkest)` overrides are impossible — the bundle does not emit any `--brand*` variables.
4. **`brandDark` (`#1f6647`) is shared.** Verified inline-styles in the rendered DOM:
   - Play button wrapper: `background-color: rgb(31, 102, 71)`
   - Progress bar fill: `background-color: rgba(31, 102, 71, 0.3)`
   - Progress thumb: `background-color: rgb(31, 102, 71)`
   - Ghost thumb (preview): `background-color: rgba(31, 102, 71, 0.8)`

   The tab panel background visible in the user's screenshot is the same dark-green shade as the play button. So almost certainly **the tab panel bg uses the same `brandDark` token**. Changing `brandDark` would also break the play button visual identity.

5. **`brandDarkest` is either unused for the panel bg, or has a fallback path** that kicks in when it's too light to contrast with text. Either way, the user's token change to `brandDarkest=#e6f0dc` did not paint anything in the rendered output.

6. **The template is delivered via Mustache rendering, sanitized through DOMPurify, then compiled by Vue.** `<style>` is forbidden by DOMPurify (Attempt 1 evidence). Inline `style="…"` attributes survive (Attempt 2 evidence — our wrapper styling does render).

7. **The player iframe is same-origin** — the parent's `iframe.contentDocument` is accessible without cross-origin errors (the Playwright probe accessed it freely).

### Locations

- Player template: `django_chat/templates/cast/django_chat/player_template.html`
- Audio embed include: `django_chat/templates/cast/django_chat/audio.html`
- Player config theme override: `config/settings/base.py:279-292` (`CAST_PODLOVE_PLAYER_THEMES`)
- django-cast Podlove config builder: `.venv/lib/python3.14/site-packages/cast/podlove.py` (read-only third-party code)
- Default Podlove theme tokens in django-cast: same file, `DEFAULT_PODLOVE_THEME` constant
- Player bundle (~138 KB minified, multi-chunk via webpack): `staticfiles/cast/js/web-player/embed.5.js`
- Page-level player loader (parent side, we own): `django_chat/static/django_chat/js/podlove-loader.js`
- Site CSS (parent side, we own): `django_chat/static/django_chat/css/site.css` — already has rules at lines 2450-3072 that target the player's wrapper iframe element from the parent. These rules style the iframe wrapper, **not** the iframe's inner document.
- Spec and plan: `docs/superpowers/specs/2026-05-16-player-design-cleanup-design.md` and `docs/superpowers/plans/2026-05-16-player-design-cleanup.md`
- Playwright probe script: `/tmp/inspect_player.py` (reusable for further inspection — assumes dev server at `http://localhost:8001`)

### Where Podlove docs were unhelpful

- <https://docs.podlove.org/podlove-web-player/v5/templating/getting-started/> — doesn't mention DOMPurify, `<style>`, or arbitrary HTML inside templates.
- <https://docs.podlove.org/podlove-web-player/v5/templating/components/root/> — describes `<root>` as accepting "player components" with Tailwind classes but doesn't enumerate what survives the sanitizer.

The docs are silent on customization beyond theme tokens and Tailwind utility classes inside the template.

## Questions for you

1. **Is there an officially-supported way to inject custom CSS into the Podlove Web Player v5 iframe?** Look for: a config field (something like `customCss`, `additionalStylesheet`, `themeCss`, `stylesheet`), a documented template directive, a runtime API on the `<podlove-player>` custom element, or a CSS variable contract we haven't found. Search Podlove's GitHub repos (org `podlove`, especially `podlove-web-player`), changelogs, and community discussions.

2. **Does Podlove v5 have an additional theme token we're missing** that paints the tab content background separately from `brandDark`? The 8-token set (`brand`, `brandDark`, `brandDarkest`, `brandLightest`, `shadeDark`, `shadeBase`, `contrast`, `alt`) is what django-cast's config builder exposes — but maybe Podlove v5's actual config schema accepts more.

3. **Has anyone else done a tab-panel restyle without forking?** Search GitHub for projects using Podlove Web Player v5 with custom CSS injected into the iframe (e.g., a CSS file referenced from `<head>` of the rendered iframe document). Public examples we can learn from.

4. **What is the cost of forking `embed.5.js`?** It's served from django-cast's static files (`.venv/lib/python3.14/site-packages/cast/static/cast/js/web-player/embed.5.js`). Could django-cast be configured to load an override copy from this project's own static files? What does upstream upgrade churn look like — is the bundle structure stable across Podlove minor versions, or does it change shape per release?

5. **JS injection feasibility.** Given the iframe is same-origin and we own `podlove-loader.js`, evaluating this approach: when the iframe load event fires, append a `<style>` element to `iframe.contentDocument.head` with the override rules. Pros vs. cons? Race-condition risks (Vue not yet mounted, hydration overwrite)? Selector stability vs. Podlove version bumps (since the rendered classes are Vue-generated)? Is this what other sites do in practice?

6. **Non-iframe deployment mode.** Does Podlove v5 offer a "shadowless" / "no-iframe" embed where the player renders in the parent DOM? Search for it. If yes, we'd be able to use plain site.css to style the inner panel — at the cost of the parent's CSS leaking into the player. What are the tradeoffs?

7. **Given all the above, what is your recommended path forward?** Rank-order: cheapest viable approach first, with realistic effort estimate (hours) and biggest risk for each. The user values low-risk, ship-able outcomes over comprehensive solutions; "deliver readable transcript text without breaking the play button" is the must-have, the close-button / Follow-button match is a nice-to-have.

## Output expected

A written research report covering:

- A direct answer to each numbered question with citations (URLs, file paths, code excerpts).
- A clear, ranked recommendation for what to do next. State the approach, the change it implies in our codebase, the realistic effort, and the biggest risk.
- An explicit list of dead ends you confirmed so we don't re-try them.

Do **not** edit any code in this repo, do **not** open a PR, do **not** invoke implementation skills. Research only. End your turn with the report.
