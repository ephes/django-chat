# CSS Architecture

This document describes how `django_chat/static/django_chat/css/site.css` is
organised, the conventions for naming tokens and classes, and the rules for
extending the stylesheet without breaking its structure. The stylesheet is
hand-authored: there is no preprocessor, no CSS modules, no Tailwind, and no
build-time splitter. Cascade layers, custom properties, and modern selectors
do the structural work.

## Browser baseline

Supported floor: **iOS / Safari 16+**, recent Firefox and Chromium. Anything
older is out of scope; do not add polyfills, JS shims, or `@supports` blocks
for pre-16 Safari. The only Safari 16 split we currently work around is
`color-mix()`, which landed in 16.2 — see [Color tokens and `color-mix()`
fallbacks](#color-tokens-and-color-mix-fallbacks).

## Cascade layer structure

The stylesheet declares a single explicit layer order near the top:

```css
@layer base, components, podlove, modals;
```

Later layers win over earlier ones regardless of selector specificity, and
**unlayered rules win over everything in layers**. We use this so the
view-transition pseudo-element rules and `@keyframes` (which the browser
needs to look up by name regardless of cascade position) always apply.

### Layer responsibilities

| Layer        | Owns                                                                                                                       |
|--------------|----------------------------------------------------------------------------------------------------------------------------|
| `base`       | Tokens (`:root`), resets, typography, `html`/`body`, sticky-footer skeleton, `.site-header`, `.site-nav`, `.site-footer`. |
| `components` | Ordinary site components: `.show-*`, `.episode-*`, `.filter-*`, `.feed-*`, `.subscribe-*`, `.sponsor-*`, `.transcript-*`, page-header pattern, layout primitives, pagination, status pages, cards. |
| `podlove`    | `.audio-panel`, the Podlove player facade, Podlove vendor-shadow overrides, and the Podlove-specific mobile container query. |
| `modals`     | Share dialog, embed dialog, their overlay/`::backdrop` styling and animation. |

### Unlayered, on purpose

These rules sit **outside** any layer and must not be moved into one:

- `@font-face` declarations (Roboto, Roboto Mono, Ubuntu).
- `@view-transition { navigation: auto }`.
- `::view-transition-*` pseudo-element rules (`-group`, `-old`, `-new`) plus
  their `@media (prefers-reduced-motion: …)` siblings.
- `@keyframes dc-vt-*` definitions used by the pseudo-element rules.

Why unlayered: view-transition pseudo-elements live on the document root,
not inside `.site-*`/`.episode-*` markup, so component-layer overrides can
unintentionally lower their priority. Keeping them unlayered means
`prefers-reduced-motion: reduce` can collapse them to 1ms reliably, and we
do not have to chase specificity bugs from inside the layered cascade.
`@font-face` is unlayered because font-face descriptors are global and
identity-keyed; wrapping them in a layer adds nothing.

### Reopening layers

The same layer name may be reopened any number of times. The file does this
on purpose: `components` is reopened after the view-transition block, then
again after the podlove mobile block, etc. The layer order declared at the
top of the file fixes the cascade — reopening only appends rules to the
named bucket. Treat layer boundaries as the architectural seam:

- A component rule that belongs to a particular layer must live inside that
  layer's brace block, even if it appears later in the file.
- Do not "lift" a rule into a different layer to win a specificity battle —
  fix the selector instead.
- Do not introduce a new layer name without a real architectural reason.

## Token naming

All globally exposed design tokens use the `--dc-*` prefix. The prefix marks
"this is a Django Chat design token" and prevents collisions with vendor
custom properties from Podlove or Wagtail.

Examples:

- Colours: `--dc-ink`, `--dc-paper`, `--dc-django`, `--dc-accent-dark`,
  `--dc-surface-deep`, `--dc-surface-django-tint`, `--dc-error`.
- Surfaces and textures: `--dc-paper-texture`.
- Geometry: `--dc-radius`, `--dc-radius-pill`, `--dc-tap`, `--dc-gutter`,
  `--dc-container`, `--dc-topbar-h`, `--dc-aside-width`,
  `--dc-aside-column-gap`, `--dc-measure`. `--dc-gutter` is the
  single-source-of-truth page edge inset: 1rem on phones, bumped to 2rem
  from 600 px upward via one media query in `:root`. Every site-wide
  breakout pattern reads `var(--dc-gutter)`; do not re-introduce literal
  `16px` / `32px` gutters at call sites.
- Motion / focus / shadow: `--dc-transition-colors`, `--dc-focus-ring-soft`,
  `--dc-focus-outline`, `--dc-shadow-sm` … `--dc-shadow-xl`.

### Deliberate exceptions

- **Spacing scale** (`--s-3` … `--s5`): single-source-of-truth scale, used
  on practically every component. The deliberately short names keep grid
  and padding declarations readable. Do not rename to `--dc-s-*`.
- **Typography scale** (`--text-*`, `--weight-*`, `--leading-*`,
  `--tracking-*`, `--font-*`): a small, self-contained type system; the
  prefix encodes the role (`--text-` for size, `--leading-` for
  line-height) and the short names compose well with component overrides.
- **Component-local variables** (`--page-header-shape-width`,
  `--episode-cover-size`, `--episode-sticky-gap`, `--player-*`,
  `--cluster-space`, `--cluster-justify`, `--stack-space`, `--grid-min`,
  `--grid-space`, `--platform-icon-url`, …): these are scoped to one
  component or one layout primitive and never read from outside it. They
  intentionally stay un-prefixed because their scope is local.

When in doubt, ask: would another component ever read this variable? If
yes, it belongs in `:root` with the `--dc-` prefix. If no, keep it local
and unprefixed.

## Color tokens and `color-mix()` fallbacks

`color-mix()` shipped in Safari 16.2. For tokens that must paint a visible
surface on Safari 16.0/16.1, pair the modern declaration with a
hand-computed `rgb()` fallback declared immediately above it, e.g.:

```css
--dc-django-soft: rgb(14 163 66 / 0.08);
--dc-django-soft: color-mix(in srgb, var(--dc-django) 8%, transparent);
```

Browsers that do not understand the second declaration keep the first
declaration's value; supporting browsers override it. The currently
fallback-paired tokens are:

- `--dc-django-soft`, `--dc-django-tint`
- `--dc-focus-ring-soft`, `--dc-focus-outline`
- `--dc-shadow-sm`, `--dc-shadow-md`, `--dc-shadow-lg`, `--dc-shadow-xl`

Keep the literal `rgb()` value in sync with `--dc-django` (#0ea342 →
14 163 66) and `--dc-ink` (#0d0d0d → 13 13 13). One-off `color-mix()`
calls in component rules do **not** need a fallback unless their absence
would visibly break the page on Safari 16.0/16.1 — most are
progressive-enhancement detail (subtle overlays, decorative drop-shadows)
that can degrade silently.

## Class naming

### Domain prefixes (preferred)

Component classes use a domain prefix that maps to the feature they belong
to. New components should pick the most specific prefix that fits:

- `.site-*` — global chrome (header, nav, footer).
- `.show-*` — the podcast hero and surrounding shell.
- `.episode-*` — episode list rows, hero, sidebar, sections, badges.
- `.filter-*` — search, date-picker, filter form, popover.
- `.feed-*` — RSS-discovery page and feed-action buttons.
- `.subscribe-*` — subscribe landing page.
- `.sponsor-*` — sponsor page and sponsor CTA.
- `.share-*` — share modal, copy-link UI, mastodon share row.
- `.embed-*` — embed modal and the embed-only stylesheet.
- `.transcript-*` — transcript section and view.
- `.page-header-*` — reusable subpage header pattern.
- `.pagination-*`, `.platform-*`, `.audio-*`.

### Modifiers

Modifiers use the BEM-style double-dash suffix and read as "this variant of
the base component":

- `.feed-action--primary`
- `.show-artwork--default`
- `.filter-search--with-clear`
- `.episode-number-badge--detail`

Do **not** use `--` for state. State classes use the `.is-*` prefix (or, in
a couple of progressive-enhancement cases, `.has-*`):

- `.is-open`, `.is-selected`, `.is-empty`, `.is-today`, `.is-revealed`,
  `.is-outside-month`.
- `.has-js-stats` — opt-in capability flag toggled by a tiny script when JS
  is available; the no-JS path simply does not get the enhancement.

### Layout primitives

Layout primitives stay short on purpose — they are composable building
blocks and appear all over the markup as combo classes:

- `.stack` — vertical rhythm via flexbox+gap (`--stack-space` API).
- `.cluster` — wrapping horizontal group (`--cluster-space`,
  `--cluster-justify`, `--cluster-align`).
- `.grid-auto` — auto-fit responsive grid (`--grid-min`, `--grid-space`).

Layout configuration belongs on the component class via the custom-property
API, not in inline styles. Reach for an Every-Layout-style primitive before
hand-rolling another media query.

### Globally available atoms / legacy globals

A small number of classes are intentionally **un-prefixed** because they are
either single-purpose atoms used everywhere or pre-existing global
components we have not renamed:

- `.eyebrow`, `.back-link`, `.no-results`, `.visually-hidden`,
  `.button-primary`, `.button-icon`, `.card`.
- `.page-content` — centered 1120-px container shared by every page
  template's inner wrapper. The outer `<main class="site-content">` in
  `base.html` stays viewport-wide so the page-header bubble and any
  full-bleed sections can occupy the full row; `.page-content` is the
  inner element that supplies the container width and centering.
- `.skip-link` — keyboard-only "skip to main content" anchor, the first
  element inside `<body>`. Off-screen until `:focus-visible`, then docks
  at the top-left corner above the sticky header. Target is `#main-content`
  on the outer `<main class="site-content">`.

Treat these as a closed set. New work should reach for a domain-prefixed
class instead of growing the global list.

## JS and data hooks

- **Styling hooks are classes.** Use CSS class selectors for visual rules.
- **Behaviour hooks are `data-*` attributes.** When a script needs to find,
  measure, or operate on a node, it queries `data-*` attributes — `[data-vt-
  page]`, `[data-vt-episode-slug]`, `[data-vt-episode-badge]`,
  `[data-copied]`, `[data-template]`, `[data-vt-same-pagination]`, etc.
- Do not couple visual rules to `data-*` attributes unless the attribute is
  the truthy/falsy state itself (`.feed-action[data-copied]` is fine — the
  attribute *is* the state). Otherwise add an `.is-*` class.
- **JS adds polish, not access.** Core content and primary actions must work
  with JS disabled. The share modal, the filter form, and the header
  auto-hide are wired so the no-JS path still functions; new components
  must keep that contract.

## Vendor / Podlove rules

- Podlove component styling and vendor-shadow overrides belong in the
  `podlove` layer. That covers the player facade, layout, colours,
  `.audio-panel` chrome, and any rule that targets `.podlove-*` classes for
  visual reasons.
- Cross-cutting **global policies** may still mention Podlove selectors
  when the rule applies site-wide. Examples in `base` today: the
  view-transition opt-out (`view-transition-name: none` on `.audio-panel`,
  `podlove-player`, and their descendants so the player never participates
  in view transitions) and the cursor-pointer policy that lists every real
  `<button>` selector on the site, including the Podlove player button.
  These are part of a global rule, not Podlove styling, and stay in `base`.
- **Do not rename Podlove classes** — they come from the vendor element's
  shadow-DOM template. Override them by selector instead.
- Keep `!important` declarations local to Podlove overrides. Outside the
  vendor layer they are a code smell.

## Pattern rules

### Surfaces and cards

Reach for the existing tokens before introducing new ones:

- `--dc-paper-texture` for the paper-stock background image used by the
  main content area and section bleeds. Always paired with
  `background-attachment: fixed` and an explicit `background-color`.
- `--dc-surface-django-tint` for opaque pale-green surfaces.
- `--dc-django-soft` / `--dc-django-tint` for translucent green hover/focus
  surfaces.
- `--dc-shadow-sm` … `--dc-shadow-xl` for elevation. Adjust the offset only
  if a component needs a deliberately different physics; do not invent a
  parallel shadow scale.

### Focus

Use `--dc-focus-outline` (with `outline-offset: 3px`) for keyboard focus
rings on real focusable elements. The `--dc-focus-ring-soft` shadow token
is for surfaces that need a halo without an outline (cards, popovers).

### Full-bleed sections

The repeated `width: 100vw; margin-left: calc(50% - 50vw); margin-right:
calc(50% - 50vw);` pattern is intentional — it lives wherever a section
needs to escape the centered `.page-content` wrapper. The outer
`<main class="site-content">` is already viewport-wide, so full-bleed
sections that live outside `.page-content` (e.g. `.page-header-wrap`,
`.show-hero`) don't need the trick at all; the trick is only needed for
sections nested inside `.page-content` that still need to break out
(`.platform-band`, `.filter-form`, `.sponsor-stats::before`, …). Do not
extract it into a utility class without a clear reason; the lines are
easier to read in
place than dereferenced through a name.

### Modals

The share and embed modals follow the same two-mode pattern: JS path uses
`dialog.showModal()` + `::backdrop`; no-JS path uses `:target`. Keep both
paths working when adding a new modal.

## Buttons

Buttons are **deliberately contextual**. There is no `.btn` taxonomy and
should not be. The site has these button surfaces today, each with its
own colour, padding, and hover treatment:

- `.button-primary` — the default ink/accent solid pill.
- `.feed-action`, `.feed-action--primary` — feed page actions.
- `.share-pill` — share-modal trigger buttons.
- `.filter-clear-all` — filter form "clear" pill.
- `.sponsor-cta-button` — sponsor page CTA.
- `.footer-mastodon-button` — footer fediverse follow button.
- `.platform-band-links a` — directory link pills.
- `.pagination-nav a` — pagination prev/next pills.

The shared *anatomy* (rounded shape, inline-flex alignment, no underline) is
factored out into a single grouped selector near the top of the `components`
layer; per-class rules supply colour, padding, font, and hover state. **Do
not** introduce a `.btn-primary` / `.btn-secondary` / `.btn-ghost` system on
top of this — the contextual classes are the API, and unifying them would
make every button page-specific override a fight against the abstraction.

## Do / don't

**Do:**

- Use the `@layer` the component belongs to. Reopen the layer if needed.
- Use `--dc-*` tokens for any value that crosses component boundaries.
- Compose with `.stack`, `.cluster`, `.grid-auto` before reaching for a
  media query.
- Solve UI problems in CSS first; treat JS as progressive enhancement.
- Pair `color-mix()` tokens with an `rgb()` fallback when they paint a
  visible surface that must work on Safari 16.0/16.1.
- Add Safari 16-specific workarounds with a short inline comment that
  documents *why*.

**Don't:**

- Don't move `@font-face`, `@view-transition`, `::view-transition-*`, or
  `@keyframes dc-vt-*` rules into a layer.
- Don't change the order of `@layer base, components, podlove, modals;`.
- Don't introduce a generic button system or rename the contextual button
  classes.
- Don't rename Podlove (`.podlove-*`) classes.
- Don't add support for browsers below iOS/Safari 16.
- Don't grow the global un-prefixed class list (`.eyebrow`, `.back-link`,
  `.card`, …). New components get a domain prefix.
- Don't couple visual rules to `data-*` attributes unless the attribute *is*
  the state.
- Don't promote a one-off value into a `--dc-*` token until at least two
  components share it.
