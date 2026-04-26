# Visual Polish — Staging Design

Spec for the visual polish pass on the Django Chat staging site, expanding
slice 6 of `2026-04-18_django-chat_research.md`. Tracked as the next action
in `docs/implementation-status.md`. Goal: hosts review staging and
recognise it as Django Chat without flagging "this looks unfinished."

This is a single, bundled change — visual identity, search/facet UI, and
the Podlove player land together so hosts evaluate the whole experience
in one round.

## Goals

- Spirit parity with `djangochat.com` — match palette, typography, hero
  composition, and single-column episode-row layout closely enough that
  hosts read it as the same show. Not pixel-perfect parity; specific
  choices that diverge are called out in the Approach section.
- Wire the Podlove web player on episode pages so audio playback looks
  finished, not browser-default.
- Expose django-cast's filterset (text search, date range, date facets,
  ordering) on the episode list page — required for navigating ~200
  episodes.
- Ship favicon, basic Open Graph / Twitter metadata.
- Keep public URL shape unchanged. No backend route changes.

## Non-goals

- Transcript page polish (separate slice in `implementation-status.md`).
- Dark mode, animations, scroll effects, page transitions.
- Mobile redesign beyond the existing 760px breakpoint.
- Wagtail admin login skin.
- Per-episode artwork (Simplecast doesn't expose it; the show artwork is
  reused everywhere djangochat.com itself reuses it).
- A custom Vite/Node build pipeline. We consume django-cast's prebuilt
  Vite manifest via `django-vite` only.
- Comments, related-episode lists, sponsor blocks on episode detail.

## Approach

Approach **B — spirit parity** (chosen over high-fidelity pixel parity
and "inspired-by, not parity"). Match djangochat.com's palette,
typography, hero composition, and single-column episode-row layout. Do
*not* replicate the Simplecast-style "Details / Transcript" tab UI on
the episode page — transcript stays at its own URL
(`/episodes/<slug>/transcript/`). Search and faceted navigation sit
cleanly above the episode list as first-class features rather than
retrofits.

Reference grounding:

- djangochat.com is a Simplecast SPA shell. WebFetch and curl return
  empty JS containers. Layout truth was captured by a Playwright
  screenshot run against the live site (homepage + the
  `django-tasks-jake-howard` episode page).
- Typography is sourced from the `<link>` tag in djangochat.com's HTML
  shell: Roboto, Roboto Flex, Roboto Mono via Google Fonts.
- Brand colour `#0D0D0D` comes from the imported site fixture
  (`simplecast_site.json`'s `color` field), confirmed against the
  screenshots.

## Visual language tokens

Defined in `django_chat/static/django_chat/css/site.css` as CSS custom
properties.

```
--dc-ink:    #0D0D0D   /* primary ink, header bg, primary button bg */
--dc-paper:  #FFFFFF   /* body bg */
--dc-muted:  #5d6673   /* secondary text */
--dc-line:   #ececec   /* hairline dividers, input borders */
--dc-link:   #0E7C7B   /* link accent, matches djangochat link colour */
--dc-django: #44B78B   /* used only inside the show artwork mark */
```

Drops the existing `--dc-green`, `--dc-blue`, `--dc-red`, `--dc-panel`
tokens — they don't appear in djangochat.com's palette.

Type stack:

- Display (hero title): Roboto Flex 900, ~56px on desktop,
  letter-spacing −0.025em, line-height 1.0.
- Page title (episode detail): Roboto Flex 800, ~36px, letter-spacing
  −0.02em.
- Row title (episode list, show notes h2): Roboto 700, 20–22px.
- Body: Roboto 400, 16px / 1.55.
- Eyebrow / metadata: Roboto Mono 500, 12px, uppercase,
  letter-spacing 0.06em.

Fonts are self-hosted (`woff2` files in `django_chat/static/fonts/`,
`@font-face` rules with `font-display: swap`). No third-party Google
Fonts request at runtime. Use `django-google-fonts` to fetch the files
once at design time, or download manually — implementation detail
resolved at plan time.

Spacing and surface decisions:

- Container width: `min(1120px, 100% - 32px)` (unchanged).
- Section vertical rhythm: 56px top / 36px bottom on the show hero;
  72px top on the episode list.
- Surfaces: hairline dividers between episode rows, no card backgrounds.
- Border radius: 4px on chrome (down from 8) for a flatter feel.

## Site shell (`base.html`, footer, favicon, metadata)

Header (`.site-header` in `base.html`):

- Black bar (`--dc-ink`), 64px tall.
- Left: 36px square show artwork (replaces the `DC` text badge) +
  "Django Chat" wordmark in white Roboto 700.
- Right: nav links (Episodes + `source_metadata.visible_menu_links`),
  white Roboto 600 14px.

Footer (`.site-footer`):

- Black bar matching header.
- Left: small wordmark + tagline (`show.subtitle` if present).
- Right: `source_metadata.visible_social_links`.
- Tiny "Powered by django-cast" attribution linking to django-cast's
  GitHub.

Favicon and icons:

- Generate `favicon.ico`, `favicon.svg`, `apple-touch-icon.png` from the
  imported show artwork. Ship as static files in
  `django_chat/static/django_chat/`. Generation is a one-shot
  out-of-band step (small script or manual); not a runtime concern.
- Wire in `base.html` head with the canonical `<link rel="icon">`
  triplet.

Open Graph / Twitter metadata (extension to `{% block meta %}`):

- `og:site_name = "Django Chat"`
- `og:title` (defaults to page title)
- `og:description` (defaults to `page.search_description` or show
  description)
- `og:image` (show artwork URL)
- `og:url` (canonical URL, already resolved in the existing template)
- `og:type = "website"` on list/show pages, `"article"` on episode
  detail
- `twitter:card = "summary_large_image"`

Each is a Django template `{% block %}` so episode detail can override
title/description/image without duplicating the head.

## Episode list page (`blog_list_of_posts.html`)

Composition top-to-bottom:

1. **Show hero** (white bg, two-column on desktop, stacks on mobile):
   - Left col: eyebrow ("A biweekly podcast"), display title from
     `page.title`, tagline from `page.description`, two CTAs:
     - "Apple Podcasts" — outlined button, links to the Apple
       distribution channel from
       `source_metadata.visible_distribution_links`.
     - "Listen & Subscribe" — black-filled button. Links to the
       Simplecast site root if present in distribution links, else
       falls back to the podcast RSS feed URL.
   - Right col: square show artwork at `min(280px, 35vw)`,
     `border-radius: 4px`, soft shadow.

2. **Distribution link band** (existing): pill row of
   `visible_distribution_links` between hairline borders. Restyled —
   drop the green-tinted background, use plain white with `--dc-ink`
   text and `--dc-line` border.

3. **Filter form** (`_filter_form.html` partial, new):
   - Inputs: text `search`, `date_after`, `date_before`, `date_facets`
     dropdown, `o` ordering dropdown, "Filter" submit button.
   - Single-row layout on desktop, stacks on mobile.
   - Renders `filterset.form` from the django-cast blog view's context.
     Guarded with `{% if filterset %}` so non-cast Page types render
     nothing.
   - Style: light surface (`--dc-paper`), `--dc-line` borders on inputs,
     `--dc-ink` filled submit button.

4. **Episode rows** (single column — replaces the current
   `repeat(2, minmax(0, 1fr))` grid):
   - Per row: 32px play-circle icon (visual only; whole row is wrapped
     in `<a href="{{ post.page_url }}">`), then a column with eyebrow
     meta, title H3, 2-line clamped description.
   - Eyebrow format: `{visible_date} · S{season} E{number} · {duration}`
     — falls back to `{visible_date}` alone if season/episode/duration
     aren't persisted on the imported model (see Open Question).
   - Hairline divider between rows. No card backgrounds.

5. **Pagination** (existing `pagination.html`, restyled): Prev / page
   indicator / Next, centred, 56px top padding.

6. **Empty / no-results state**: if filtering returns no rows, render
   "No episodes match your filters." with a "Clear filters" link
   pointing back to `{{ blog_url }}`. Unfiltered empty state shows a
   neutral placeholder.

## Episode detail page (`episode.html`)

Composition top-to-bottom:

1. **"← Back to Episodes"** — small text link.

2. **Two-column hero** (white bg, stacks on mobile):
   - Left: square show artwork (~280px), `border-radius: 4px`, soft
     shadow.
   - Right: eyebrow meta line (`{visible_date} · S{season} E{number} ·
     {duration}`), page title H1 (Roboto Flex 800, 36px), small
     icon-link row — SHARE / FACEBOOK / TWITTER / DOWNLOAD MP3.
     "Subscribe" is dropped from this row (it lives on the show hero,
     not per episode).

3. **Podlove player** — replaces the manual `<audio controls>` element
   currently at `episode.html:17`:
   - Drop the explicit `<audio>` tag from `episode.html`.
   - Render via the `audio` StreamBlock in `page.body`. django-cast's
     `cast/templates/cast/audio/audio.html` partial emits the full
     Podlove markup including `data-url` (config endpoint) and
     `data-embed` (classic embed script) attributes.
   - Set `CAST_PODLOVE_LOAD_MODE = "facade"` in settings. The page
     renders a static "fake player" facade until the user clicks; only
     then does the heavy Podlove JS load. This is the perf path — no
     bundle on initial page load.
   - Add `{% load django_vite %}` and
     `{% vite_asset 'src/audio/podlove-player.ts' app="cast" %}` in
     `{% block javascript %}`. The asset tag emits a hashed
     `<script type="module">` resolved from django-cast's prebuilt
     manifest.
   - **Stretch**: theme the Podlove player by overriding tokens via
     `cast.podlove.build_podlove_player_config` (brand → `--dc-ink`,
     fonts → Roboto). Default theme is acceptable if theming proves
     fiddly during implementation.

4. **Show notes** (from `page.body`):
   - Section headings (`<h2>` / `<h3>` from richtext blocks): Roboto
     700.
   - Bulleted lists with comfortable line-height; links in `--dc-link`.
   - Content width capped at ~720px for readability.

5. **Transcript link**: when `episode.transcript` exists, render a plain
   text link in the eyebrow row pointing at
   `{% url 'cast:episode-transcript' slug=page.slug %}`. No tab UI.

## Player infrastructure (django-vite)

Setup (mirrors the python-podcast pattern):

- Add `django-vite` to `pyproject.toml` via `uv add django-vite`. No
  Node toolchain enters the repo.
- Add `"django_vite"` to `INSTALLED_APPS` after
  `"django.contrib.staticfiles"`.
- In `config/settings/base.py`:

  ```python
  import cast
  from pathlib import Path

  _CAST_PKG_DIR = Path(cast.__file__).parent

  DJANGO_VITE_DEV_MODE = env.bool("DJANGO_VITE_DEV_MODE", default=False)
  DJANGO_VITE = {
      "cast": {
          "dev_mode": DJANGO_VITE_DEV_MODE,
          "static_url_prefix": "" if DJANGO_VITE_DEV_MODE else "cast/vite/",
          "manifest_path": _CAST_PKG_DIR / "static" / "cast" / "vite" / "manifest.json",
      },
  }
  DJANGO_VITE_ASSETS_PATH = "need to be set but doesn't matter"
  ```

  This points at the prebuilt Vite manifest shipped inside the
  django-cast Python package. We do not run Vite ourselves.

- `dev_mode` stays `False` everywhere — there is no HMR target to
  connect to. The setting is parameterised so future work could plug in
  a local Vite dev server, but that is out of scope.

- `collectstatic` already picks up `cast/static/cast/vite/*.js` because
  django-cast is an installed app. No additional collection config.

- Deploy: zero changes. CI doesn't gain a Node step; the deploy
  artefact gains one Python dependency.

## Error pages

`400.html`, `403.html`, `403_csrf.html`, `404.html`, `500.html` each
extend the new branded `base.html`. Body is a single centred block:
H1 (page title), one-line description, "Back to episodes" link
pointing at `{% url 'cast:episode-list' %}` (or the podcast root —
whichever resolves on the source site). No illustrations, no
marketing copy. Each file should be ~10 lines.

## Testing & verification

Unit / template tests (extend `django_chat/tests/`):

- Render the episode list page; assert presence of: hero title,
  distribution link band, filter form fields (`search`, `date_after`,
  `date_before`, `date_facets`, `o`, submit), at least one episode row
  with eyebrow meta and title, pagination markup.
- Render the episode detail page; assert: page title H1, eyebrow meta,
  Podlove markup container with `data-url` pointing at the
  `cast:api:audio_podlove_detail` URL, no raw `<audio>` element, the
  `vite_asset` script tag is present.
- Render `base.html`; assert: favicon `<link>` triplet, OG tags
  (`og:site_name`, `og:title`, `og:image`, `og:type`), self-hosted
  font `@font-face` references in the loaded CSS.

Filterset integration:

- `GET /episodes/?search=django` returns a filtered queryset (use a
  fixture episode whose title or body contains "django").
- `GET /episodes/?o=visible_date` orders results ascending by date.

Player smoke:

- `python manage.py collectstatic --dry-run --noinput` lists
  `cast/vite/podlovePlayer-*.js`.
- The `vite_asset` tag renders without raising (covered by the
  template render test above).

Visual verification:

- Repeat the Playwright screenshot script against staging
  (`https://djangochat.staging.django-cast.com/` and one episode
  page). Compare visually to the saved djangochat.com screenshots in
  `/tmp/`. Human review, not automated diff.

Lighthouse smoke (one-time, on staging):

- After deploy, run Lighthouse against an episode page; performance
  score should be > 80. Facade mode means the heavy Podlove JS is not
  in the initial bundle. Not a regression gate, just a sanity check.

Existing suite stays green:

- `just test` and `just lint` pass with no new failures.

## Open question (resolved at plan time, not now)

Are season number, episode number, and duration persisted on the
imported `Post` / `Episode` model? If yes, the eyebrow line uses them.
If no, two fallbacks:

- Extend the import to capture them from the Simplecast detail
  payload (the fixtures already include `episode_number`, `season`,
  and `duration_in_seconds` on the source side).
- Drop them from the eyebrow line and show only `{visible_date}`.

Resolution belongs in the implementation plan, not this design.

## What this slice does not change

- Public URL shape (`/`, `/episodes/`, `/episodes/<slug>`,
  `/episodes/<slug>/transcript/`).
- Import command behaviour or fixtures.
- Backend models or migrations (modulo the open question above, which
  may add fields).
- Wagtail admin templates, forms, or workflows.
- Deploy automation, CI, or secrets handling.
