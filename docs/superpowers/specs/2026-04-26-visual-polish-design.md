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
- Keep public URL shape unchanged. URL patterns and route names stay
  put; the existing `podcast_episode_index` view is extended, not
  replaced (see "What this slice does change in the backend").

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
   - Renders `filterset.form`. **The current `/episodes/` route is a
     custom view at `django_chat/core/views.py:12`
     (`podcast_episode_index`) that builds `posts` by hand, ignores
     `request.GET`, and sets `is_paginated=False`. To make the filter
     form functional, this view must be extended to:**
     1. Instantiate `cast.filters.PostFilterset(request.GET,
        queryset=Episode.objects.live().child_of(podcast)
        .order_by("-visible_date"), request=request)`.
     2. Use `filterset.qs` as the base queryset.
     3. Paginate via `django.core.paginator.Paginator` (page-size
        TBD at plan time, e.g. 20). Set `is_paginated=True` and pass
        `page_obj` / `paginator` into context.
     4. Add `filterset` to the render context.
   - Guard the partial with `{% if filterset %}` so unrelated Page
     types render nothing.
   - Style: light surface (`--dc-paper`), `--dc-line` borders on inputs,
     `--dc-ink` filled submit button.

4. **Episode rows** (single column — replaces the current
   `repeat(2, minmax(0, 1fr))` grid):
   - Per row: 32px play-circle icon (visual only; whole row is wrapped
     in `<a href="{{ post.page_url }}">`), then a column with eyebrow
     meta, title H3, 2-line clamped description.
   - Eyebrow format: `{visible_date} · E{episode_number} · {duration}`
     — degrades gracefully when individual fields are missing on an
     episode (see "Eyebrow metadata: what's available" below). No
     season indicator (not persisted; out of scope).
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
   - Right: eyebrow meta line (`{visible_date} · E{episode_number} ·
     {duration}`, degrades when fields are missing), page title H1
     (Roboto Flex 800, 36px), small icon-link row — SHARE / FACEBOOK /
     TWITTER / DOWNLOAD MP3. "Subscribe" is dropped from this row (it
     lives on the show hero, not per episode).

3. **Podlove player** — replaces the manual `<audio controls>` element
   currently at `episode.html:17`:
   - Drop the explicit `<audio>` tag from `episode.html`.
   - **Important:** the importer at `django_chat/imports/import_sample.py`
     stores the audio on `Episode.podcast_audio` (a
     `ForeignKey`-style relation), not as an audio block in
     `page.body` — `_episode_body()` only emits text blocks. So the
     template must include django-cast's audio partial directly:

     ```django
     {% include "cast/audio/audio.html" with value=episode.podcast_audio page=episode podlove_load_mode="facade" %}
     ```

     This partial emits the full Podlove markup (`<podlove-player>`
     element with `data-url` pointing at
     `cast:api:audio_podlove_detail` and `data-embed` pointing at
     `cast/js/web-player/embed.5.js`).
   - `podlove_load_mode="facade"` is a template context variable
     consumed by `cast/templates/cast/audio/audio.html` — *not* a
     Django setting. With `"facade"`, the partial renders a
     lightweight static facade and only loads the heavy Podlove JS
     when the user clicks. This is the perf path — no Podlove bundle
     on initial page load.
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
   text link in the eyebrow row using the
   `episode_transcript_url` context variable already populated by
   `cast.models.pages.Episode.get_context()`. If for some reason the
   variable isn't in context (e.g. a non-`Episode` view path), reverse
   manually with `{% url 'cast:episode-transcript' blog_slug=blog.slug
   episode_slug=page.slug %}` — the URL pattern requires both kwargs
   (see `cast/urls.py:33`). No tab UI.

## Player infrastructure (django-vite)

`django-vite` is **already wired** in this project — the slice does
not change settings or installed apps. Confirmed via inspection:

- `django_vite` is included in `INSTALLED_APPS` transitively through
  `cast.apps.CAST_APPS` (`config/settings/base.py:53`).
- `DJANGO_VITE` is configured for both the `cast` and `cast-bootstrap5`
  apps in `config/settings/base.py:241-254`, with `manifest_path`
  pointing at the prebuilt manifest shipped in the django-cast package.

The only change needed is **template usage**: in `episode.html`, add
`{% load django_vite %}` and emit
`{% vite_asset 'src/audio/podlove-player.ts' app="cast" %}` in
`{% block javascript %}`. The tag resolves through the existing
manifest and emits a hashed `<script type="module">` for
`cast/static/cast/vite/podlovePlayer-*.js`.

No Python deps to add, no settings to edit, no Node toolchain to
introduce. Deploy and CI are unchanged.

## Error pages

`400.html`, `403.html`, `403_csrf.html`, `404.html`, `500.html` each
extend the new branded `base.html`. Body is a single centred block:
H1 (page title), one-line description, "Back to episodes" link
pointing at `{% url 'django_chat_episode_index' %}` (the URL name
registered for `/episodes/` in `config/urls.py:24`). No
illustrations, no marketing copy. Each file should be ~10 lines.

## Testing & verification

Unit / template tests live under `django_chat/imports/tests/`
(import-adjacent assertions) and `django_chat/core/tests/` (project
view / template assertions). Extend `django_chat/core/tests/`:

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

## Eyebrow metadata: what's available

Verified against `django_chat/imports/models.py`:

- `EpisodeSourceMetadata.episode_number` — **persisted** (line 109).
- `EpisodeSourceMetadata.duration_seconds` — **persisted** (line 119).
- `EpisodeSourceMetadata.season_number` — **not persisted**, though
  `season_number` is parsed into `EpisodeSourceData` at
  `imports/source_data.py:115`. The model field would need a new
  migration plus an importer change to capture it.

Decision for this slice: the eyebrow line uses
`{visible_date} · E{episode_number} · {duration_seconds | format}`.
**Season is omitted.** Adding a `season_number` field, migration, and
import change is out of scope — explicitly tracked here so the
implementation plan does not silently grow it. If host review later
shows a need for season, that's a follow-up.

Where `episode_number` or `duration_seconds` are missing on a given
episode, degrade gracefully — show only the parts that are present.

## What this slice does not change

- Public URL shape (`/`, `/episodes/`, `/episodes/<slug>`,
  `/episodes/<slug>/transcript/`).
- Import command behaviour or fixtures.
- Backend models or migrations. (Season number is intentionally not
  added; the eyebrow line uses only fields already persisted.)
- Wagtail admin templates, forms, or workflows.
- Deploy automation, CI, or secrets handling.
- `INSTALLED_APPS`, `DJANGO_VITE`, or any other settings — django-vite
  is already wired through django-cast.

## What this slice does change in the backend

- `django_chat/core/views.py:12` (`podcast_episode_index`): extended
  to instantiate `cast.filters.PostFilterset`, apply `filterset.qs`,
  paginate the result, and pass `filterset` plus pagination context
  into the template. No model or URL changes.
