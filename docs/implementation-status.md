# Implementation Status

Lightweight status tracker for the Django Chat staging proof of concept. The
canonical scope, slice list, and acceptance criteria live in
[`2026-04-18_django-chat_research.md`](../2026-04-18_django-chat_research.md).
This file is a pointer: which slices have shipped, which acceptance criteria
are still open, and what the next agent should do.

Do not duplicate the PRD here. Update this file when a slice lands, an
acceptance criterion flips, or the next-action target changes.

## Slice Status

PRD slice list: research doc "Suggested Implementation Slices" section.

- [x] **1. Project scaffold** — `4326430` Initial Django Chat scaffold.
- [x] **2. Local settings, env loading, lint/format hooks, transcript backend
      settings, minimal tests, local-development docs** — `834d5e2`.
- [x] **3. Read-only RSS + Simplecast endpoint fixture importer with site
      menu/social/distribution link fixtures** — `02c8911`.
- [x] **4. Idempotent source metadata, sample import without audio copy** —
      `c61fbf3`.
- [x] **5. S3 media storage and audio copy for the sample import** — `a8dbae5`.
- [x] **6. Basic Django Chat branding, templates, menu links, current public
      URL compatibility** — `d24968b`. Polished `2026-04-26`
      (`32f1725`..`87edd97`): spirit-parity layout with djangochat.com,
      Roboto type stack self-hosted, Podlove player on episode detail via
      `django-vite` (init module loads `embed.5.js` on viewport
      intersection), filterset-driven search/date
      facets/ordering, favicon trio, OG/Twitter metadata, branded error
      pages. See `docs/superpowers/specs/2026-04-26-visual-polish-design.md`
      and `docs/superpowers/plans/2026-04-26-visual-polish.md`.
- [x] **6a. Compact Podlove player template for episode detail** — local
      Django Chat spike restoring the Python-Podcast-style compact player
      layout by passing `data-template=/podlove-player-template/` into
      django-cast's existing Podlove web component. The player still uses
      `cast:api:player_config` and `CAST_PODLOVE_PLAYER_THEMES`; the page
      declares a light theme so browser dark-mode preferences do not add a dark
      iframe strip below the compact controls. Later performance work added a
      Django Chat click-to-load facade so the external Podlove bundle and
      iframe wait for hover, focus, tap, or click.
- [x] **7. Smoke-level feed comparison against Simplecast RSS** — `f4fc8fc`.
      Exhaustive parity validation is deferred to production hardening per the
      PRD.
- [x] **8. Self-contained `deploy/`, clean-VPS bootstrap, SOPS/age secrets,
      role sequence `uv_install` → `traefik_deploy` → `wagtail_deploy`** —
      `7686e13`.
- [x] **9. Staging deployment, host admin accounts, host review docs** —
      `e219283`, follow-ups `d0da9f3`, `8588dd0`, `3eda73f`, `413af91`. Staging
      live at `https://djangochat.staging.django-cast.com` with copied sample
      audio served end-to-end through CloudFront.
- [x] **9a. Full-catalog import path and catalog measurement tooling** —
      live RSS + Simplecast source loader, `import_django_chat_catalog`
      with `--max-episodes`, `--dry-run`, `--copy-cover-image`, and opt-in
      streaming `--copy-audio`, plus `measure_django_chat_catalog`.
- [x] **9b. Subscribe / RSS-discovery page** — `/episodes/feed/` now renders
      the Django Chat-branded feed detail page, promotes the generated
      self-hosted podcast RSS URL (`/episodes/feed/podcast/mp3/rss.xml`),
      keeps the visible podcast feed list MP3-only because imported Django
      Chat audio is MP3-only, advertises the MP3 podcast RSS and latest
      entries RSS via `<link rel="alternate" type="application/rss+xml">`
      head metadata, and the show hero's "Subscribe" CTA points there instead
      of the Simplecast site. Imported platform links from
      `PodcastSourceMetadata.visible_distribution_links` live in the larger
      overview provider section instead of being duplicated on the subscribe
      page.
      Polished (2026-05-13) with a reusable `.page-header` pattern (inline
      SVG speech bubble with a top-dark / bottom-light gradient, horizontally
      anchored to `var(--dc-container)` so the tail keeps a fixed position
      relative to the cards on resize; new `{% block page_header %}` in the
      base template + `_page_header.html` snippet, ready to drop onto further
      subpages). The Subscribe content uses a generalised `.card` pattern for
      the "Latest entries" feature, a flat "Podcast audio feeds" list ready
      for additional audio formats, a sticky "Why RSS?" aside mirroring the
      episode-detail sidebar width, and clipboard "Copy URL" plus a
      "View XML" link next to each feed. `podcast://`/`feed://` deep-link
      buttons are conditionally shown only on iOS (where the system reliably
      hands off to Apple Podcasts / a registered reader); they are hidden by
      default on macOS, Android, Windows, and Linux because Apple Podcasts
      on macOS does not prefill the feed URL
      (developer.apple.com/forums/thread/737234) and no system handler exists
      on the other platforms.
- [x] **9c. Pre-host-review backlog cleanup** — production migration risks are
      documented in `docs/production-migration-notes.md`; episode pagination
      focuses and scrolls to the refreshed results container after same-page
      pagination; the episode filter/search controls are styled as a
      Django Chat control strip with a full clear affordance; and the Wagtail
      dependency set is upgraded to Wagtail 7.4.
- [x] **9d. Feed cutover risk analysis and plan** —
      `docs/feed-cutover-analysis.md` documents the ways a feed migration can
      break subscribers, compares the 2026-05-13 Simplecast and staging feed
      state, records the fixed no-Simplecast-redirect/S3-CDN-served-feed
      constraints, and proposes a phased cutover plan.
- [x] **9e. Show-notes heading normalization during import** — imported
      episode detail show-note labels now normalize into semantic `h3` markup
      before assignment to `page.body`; legacy imported `h4` headings are also
      normalized to `h3`. Raw source HTML in `EpisodeSourceMetadata` remains
      unchanged, and migration `imports.0004` backfills already-imported
      episode bodies without requiring a catalog reimport.
- [x] **9f. Episode keyword import from RSS item metadata** — RSS item-level
      `<itunes:keywords>` values now parse into `RssEpisode.keywords`, import
      idempotently into `Episode.keywords` through the shared sample/catalog
      path, and are covered by generated podcast feed assertions. Wagtail/taggit
      episode tags remain deliberately deferred to the separate taxonomy
      decision item.
- [x] **9g. Wagtail admin episode ordering fix** — the Podcast page's Wagtail
      child listing now defaults to imported episode `visible_date` descending,
      matching the public episode index so recent episodes do not sink below
      older pages just because import or edit timestamps differ from publish
      dates.
- [x] **9h. Episode contributors + diarized speaker labels** — django-cast
      upgraded from PyPI `0.2.56` to the `develop` branch (pinned commit
      `d6ce2c79`, reports `0.2.58`) for `Contributor`/`EpisodeContributor`
      snippets and the diarized transcript speaker-label workflow (neither is in
      any PyPI release). Migrations `0066`–`0071` applied. Episode detail pages
      render visible contributors via django-cast's `cast/contributors.html`
      partial, themed as a "Hosts and Guests" strip. The contributor HTML never
      enters list/feed output because the partial is included only by the
      detail-only `episode.html` template (feed bodies use `post_body.html`, the
      index uses card markup); the only feed change is
      additive Podcasting 2.0 `<podcast:person>` tags emitted by django-cast for
      episodes that have contributors (verified safe: channel + non-contributor
      episodes unchanged, feed still valid, item count 204). Public speaker
      labels are gated on the episode's
      visible contributors via `cast.transcript_sanitization`, identically for
      the Podlove player API and the transcript detail page. Staging episode
      `breaking-django` (audio 202) diarized via Voxhelm into Will Vincent +
      Carlton Gibson; browser-verified (Playwright) in the player transcript tab
      and the transcript detail page. See
      [`docs/contributors-and-diarization.md`](contributors-and-diarization.md).
- [x] **9i. Sponsor shout-out in show notes** — the show-notes "Sponsor"
      section is highlighted at render time by the `{% sponsor_shoutout %}`
      template tag (`django_chat/core/sponsor_shoutout.py`). The `<h3>` stays in
      flow as an ordinary section heading; the copy beneath it moves into a
      highlight box carrying a "Featured Partner of Django Chat" tab docked onto
      its top-left, plus a CTA surfaced from the sponsor's own link ("Go to
      <name>", with a domain-aware name heuristic and a neutral "Go to sponsor"
      fallback; no link → no button). Episodes without a sponsor section are
      returned byte-for-byte unchanged; on sponsor pages the surrounding show
      notes are round-tripped through the HTML parser — content-preserving and
      DOM-equivalent, though void tags / entities / attribute order may be
      normalised. The box
      outline, the tab and the CTA all use the AAA-safe `--dc-django-aaa-light`
      green; for consistency the sponsor-page `.sponsor-callout` outline and the
      hero subscribe button were aligned to the same token. Covered by
      `django_chat/core/tests/test_sponsor_shoutout.py`.
- [x] **9j. Structured show-note block UI sample slice** — django-cast is pinned
      to `f795ed5f` for `CAST_POST_BODY_BLOCKS`, and Django Chat registers
      detail-only `show_note_sponsor` and `show_note_link_list` blocks. The
      importer structures safe headed show-note sections into the block schema
      (a third block, `show_note_heading`, was added later in 9l), while feed
      rendering stays static (`h3`, `p`, `ul`, `li`, `a`)
      without icon chrome. The public UI uses decorative dark-green circular
      heading icons sized to match contributor avatars, with dark-green custom
      bullets centered under the icon column and link text aligned to the
      heading text column; source emoji prefixes are stripped from structured
      headings because the icon now supplies that visual cue. Local browser
      verification covered `django-tasks-jake-howard` and
      `djangocon-us-2025-recap` at desktop/mobile widths, with screenshots in
      `.playwright-verify/`. Paragraph-only `Support the Show` sections
      render as a single CTA list item to avoid duplicate links; multi-link
      sponsor lists are preserved as paragraph HTML instead of partially
      structuring. Link-item `description` extraction is intentionally
      deferred. The follow-up full-catalog backfill/repair landed in 9k.
- [x] **9k. Show-note backfill repair** — follow-up plan documented in
      [`docs/show-note-backfill-repair.md`](show-note-backfill-repair.md).
      Repeatable repair where `just manage migrate` fixes existing
      imported episode bodies and summary metadata on any deployed database,
      fresh imports write the corrected structure directly, and an explicit
      idempotent repair command remains available for dry-run audits and
      re-runs. The repair converts link-only unheaded HTML lists into implicit
      "Links" episode-note link lists (originally heading-hidden; later un-hidden
      to show their iconed heading — see 9l / `0018`), keeps complex source lists as source
      HTML when they contain prose around links, backfills `search_description`
      from in-database episode summaries, restores the visible `Episode Summary`
      heading on detail pages (the separate `Episode Notes` subheading was later
      unified into the page-level `Show notes` title), and converts older visibly
      legacy raw Markdown-like note bodies into rendered HTML. Follow-up
      migrations preserve paragraph-style `Support the Show` source copy
      instead of collapsing it into link-list items and rebuild affected detail
      blocks from stored source metadata; staging audit found 62 affected
      support-copy sections, and the source-vs-body text audit reports zero
      remaining missing detail phrases. Paragraph-style `Support the Show` copy
      is preserved without being collapsed into link-list items (under the later
      icon feature in 9l, the heading is offloaded into a `show_note_heading`
      block with the support icon and the copy kept as a following paragraph). A
      final support-boilerplate repair keeps the support heart icon while
      rendering the 13 known three-link support lists as a CTA sentence instead
      of bare links. Migration `0012` strips Markdown-style hash prefixes from
      recognized show-note headings, covering the isolated
      `boost-your-django-dx-adam-johnon` case where
      `###Support the Show` rendered visibly. Staging deploy and post-deploy
      dry-run on 2026-06-01 reported zero body changes, zero metadata changes,
      zero source-detail restores, zero skipped implicit lists, and zero raw
      Markdown-like bodies; Playwright verified the original affected pages,
      complex-list edge cases, raw-Markdown legacy pages, already-structured
      simple sections, and the support-boilerplate sample.
- [x] **9l. Automatic, editor-overridable show-note icons** — adds the
      `show_note_heading` block (registered alongside sponsor/link-list) so
      every real heading becomes an iconed block (D5), even non-convertible
      ones (body preserved verbatim). Each block carries a `kind` (editor
      intent, default `"auto"`, visual `IconChoiceWidget`) and a hidden,
      system-set `icon`. `kind="auto"` derives the icon from the heading via
      `resolve_icon_kind`; the concrete `icon` is **materialized at save time**
      (block `clean()` covering admin Save + Preview, the importer, and the
      data migration), with a render-time fallback for un-materialized JSON.
      Icons are code-side SVG snippets driven by `ICON_REGISTRY` and the
      `{% show_note_icon %}` tag; the picker has an admin-only JS live-preview
      of the auto-resolved icon (progressive enhancement, public site JS-free).
      Migration `0015_materialize_show_note_icons` brings existing data forward
      (icon-only, no HTML re-parse; normalises system-derived `kind` to
      `"auto"`, preserves genuine overrides — where "system-derived" also covers
      the legacy link-list default `"links"` on a differently headed link list, so
      e.g. a `Books` heading left at the default follows its heading instead of
      freezing as a links override). `0016_heal_show_note_icons` re-runs that
      corrected backfill to heal environments that applied the initially-shipped
      0015. D5 also canonicalises an offloaded known-label heading (e.g.
      `📚 Books` / `SHAMELESS PLUGS` → `Books` / `Shameless Plugs`, the icon
      replacing the source emoji); `0017_offload_raw_show_note_headings` re-runs
      the in-place structuring over imported bodies so sections left as raw
      `<h3>` HTML by pre-D5 imports become iconed heading blocks, while
      already-structured blocks and their overrides are left untouched.
      `0018_unhide_implicit_link_list_headings` reverses the earlier
      `0007_hide_implicit_link_list_headings`: implicit "Links" lists (a leading
      source list with no heading) now show their iconed heading instead of a
      bare list, since under the icon model `show_heading=False` also hid the
      icon. `0019_add_implicit_link_list_headings` closes the remaining gap a
      full staging crawl surfaced (42 episodes): a *headingless* leading list that
      is **non-convertible** (items mix prose with links / multiple anchors, so it
      cannot be cleanly itemized) was left as a bare `<ul>` with no heading or
      icon — the clean-list path and `0018` never reached it. D5 now synthesizes
      an iconed `Links` `show_note_heading` before such a list (list kept verbatim
      as a following paragraph) when it carries real links; the migration re-runs
      the idempotent in-place structuring so already-offloaded sections do not
      gain a spurious `Links` heading. See
      [`docs/structured-show-note-blocks-research.md`](structured-show-note-blocks-research.md).
      A 2026-06-03 read-only crawl of all 203 live episodes (BeautifulSoup
      structural detector over `div.show-notes`) confirmed the four classes
      0015–0018 targeted are clean — zero raw/emoji headings, zero `Episode
      Notes` leftovers, zero leaked German admin strings, zero bad/empty icon
      kinds — and surfaced this headingless-list gap on 42 episodes (a prior crawl
      missed it by only inspecting `ul[role="list"]`; these are bare `<ul>`s with
      no `role`). Replaying the new converter over those 42 episodes' lists
      produced an iconed `Links` heading for all 43 leading lists (0 still bare);
      a live staging re-crawl after deploying `0019` remains to confirm in situ.
      One unrelated one-off (`greening-django-chris-adams`) has all show notes in
      `block-overview` (detail-only structuring never reaches it) — a separate
      non-standard data state tracked as a follow-up.
- [x] **9m. Adopt upstream podcast publishing metadata** — django-cast is
      pinned to `151a4fa8` for `Season`, `Episode.episode_number`,
      `Episode.episode_type`, `Episode.season`, Wagtail panels, generated
      iTunes/Podcasting 2.0 feed tags, and opt-in automatic episode numbering
      on first publish. The shared sample/catalog import path copies positive
      imported episode numbers to canonical `cast.Episode` metadata, preserves
      the preview source value `0` only in `EpisodeSourceMetadata`, maps valid
      RSS episode types including explicit `full`, and creates/reuses
      podcast-scoped `cast.Season` rows from valid Simplecast season numbers.
      It also enables automatic numbering on the imported podcast and seeds
      `Podcast.next_episode_number` above the highest canonical episode number
      under the podcast without lowering an already advanced counter or
      re-enabling operator-disabled numbering after seeding. Public episode
      badges read canonical `Episode.episode_number` first with a
      temporary source-metadata fallback, and feed smoke checks assert positive
      `itunes:episode` / `podcast:episode` parity plus the approved preview
      omission.
- [ ] **10. Decide whether production migration needs a separate follow-up
      PRD after host review.** Decision item, not implementation; revisit after
      hosts have reviewed staging.

## Acceptance Criteria

PRD section "Acceptance Criteria For The Research Spike".

- [x] Staging site exists and loads over HTTPS.
- [x] Hosts can log into Wagtail admin (`host-review-admin` bootstrap account
      on staging).
- [x] Representative episode audio playback proven. Initially verified against
      the 8/8 copied sample; a 2026-04-29 staging catalog measurement reported
      full copied-audio coverage for the then-current 202 live episodes. A
      2026-06-02 public RSS probe found 205 current podcast items with 205
      `audio/mpeg` enclosures. Detail pages render django-cast custom
      `<cast-audio-player>` elements with a django-vite-loaded player module
      (Podlove elements before the 2026-06-11 cutover).
- [x] Public URL patterns `/`, `/episodes/`, `/episodes/<slug>`, and
      `/episodes/<slug>/transcript` represented or redirected. `/episodes/`
      and imported episode detail pages are live; generated django-cast
      transcripts are surfaced through the existing transcript route when
      attached to imported episode audio. `/episodes/preview/transcript/` and
      `/episodes/django-tasks-jake-howard/transcript/` have both been verified
      on staging.
- [x] Menu, social, and distribution links from the Simplecast site
      represented.
- [x] Transcript handling demonstrated for representative episodes.
      `/episodes/preview/transcript/` and
      `/episodes/django-tasks-jake-howard/transcript/` render
      Voxhelm-generated django-cast `Transcript` pages with Podlove JSON,
      WebVTT, and DOTe artifacts attached to episode audio.
- [x] Full catalog import path documented and repeatable. `import_django_chat_catalog`
      fetches the live RSS feed, follows Simplecast pagination/details for
      enrichment, supports limited and dry-run operator exercises, and can
      stream-copy audio without whole-MP3 reads. A real full 11 GB audio copy
      still requires explicit operator approval.
- [x] Media storage isolated from Python Podcast (separate bucket, separate
      IAM credentials, separate CloudFront distribution).
- [x] Generated podcast feed validates for imported episodes (smoke level via
      `just compare-feed`; exhaustive parity deferred to production hardening
      per PRD).
- [x] Generated podcast feed URL is surfaced for host review at
      `/episodes/feed/`, with `/episodes/feed/podcast/mp3/rss.xml` promoted as
      the primary self-hosted podcast RSS feed and advertised through RSS
      auto-discovery links in the page head.
- [x] Remaining production migration risks documented before any live
      feed/DNS change in `docs/production-migration-notes.md`.

## Where We Are

The staging proof-of-concept slices through 9k have landed on `main`. Staging
at `https://djangochat.staging.django-cast.com` is deployed and serving the
polished site:

- Black header with show artwork mark, single-column episode rows,
  Roboto type stack self-hosted, filterset search/date facets/ordering,
  branded error pages, favicon trio, OG/Twitter metadata.
- django-cast custom audio player (`<cast-audio-player>`) on episode detail,
  themed to the Django Chat green palette via the `--cast-player-*` token API
  with the in-transport share button suppressed (the sidebar Share rail item is
  the only share entry point). Episodes with an attached django-cast
  `Transcript` render the inline Transcript panel and link to the themed
  transcript route. The earlier compact Podlove player path (click-to-load
  facade, theme settings, template-proxy endpoint, loader script) was removed
  on 2026-06-11 after the staging cutover.
- Episode detail heroes render the static Django Chat SVG logo; imported show
  artwork stays attached to `Podcast.cover_image` for django-cast metadata,
  feed, and player API image paths.
- Episode-detail share and embed dialogs use a CSS `:target` fallback so they
  work without JavaScript: triggers are `<a href="#share-dialog">` /
  `<a href="#embed-dialog">`, share-pill hrefs and the embed iframe snippet
  are server-rendered, and the close link is an `<a href="#">`. When JS is
  available, it intercepts the trigger click and upgrades to a native
  top-layer `<dialog>` with focus trap, ESC-to-close, and a `::backdrop`.
  JS-only enhancements (clipboard copy, "Start at" timecode, Mastodon
  instance picker) are hidden via a `<noscript>` style block.
- Wagtail `Site` row pinned to `djangochat.staging.django-cast.com:443`
  with `TemplateBaseDirectory=django_chat`, via the new
  `ensure_default_site` post-deploy task.
- `import_django_chat_sample --copy-audio --copy-cover-image` is the
  documented operator command for a fresh staging build.
- `import_django_chat_catalog --copy-cover-image --copy-audio` is the
  documented operator command for representative full-catalog host-review
  audio state.

**Ready for full host review:**

The deployed staging site remains useful for internal smoke review of
deployment, CMS access, playback, the visual direction, and the full catalog.
It now has representative catalog/audio/feed state, Voxhelm-generated
transcript demos, documented production migration risks, pagination behavior
that returns reviewers to the refreshed episode results, and a polished
episode filter/search strip.

As of 2026-06-02, both generated staging RSS routes return HTTP 200 with 205
items. The podcast RSS route also exposes 205 `audio/mpeg` enclosures. Earlier
catalog measurement on 2026-04-29 reported full copied-audio coverage
(`live_episodes=202`, `with_audio=202`, `missing_audio=0`) before later catalog
growth.

- After each deploy or destructive staging refresh, re-check whether staging
  still holds the intended full live catalog/audio state.
- Lighthouse / Web Vitals readiness is cleared for the public host-review
  surfaces on deployed staging. The 2026-04-29 Lighthouse run measured `/`,
  `/episodes/`, `/episodes/django-tasks-jake-howard/`, and `/episodes/feed/`
  in both mobile and desktop modes with final scores of 98-100 across
  Performance, Accessibility, Best Practices, and SEO. See
  `docs/lighthouse-performance.md` for commands, artifact paths, and
  before/after scores; a 2026-06-11 re-run against the custom player scored
  99-100.
- Latest-entries feed query behavior has a scoped Django Chat mitigation.
  Staging measurement on 2026-04-29 reported `queries=620` across 202 items
  because django-cast's latest-entries feed builds podcast feeds from base
  `Post` rows, causing per-episode `specific`, `podcast_audio`, and
  `transcript` lookups. `../python-podcast` uses the same django-cast
  latest-entries implementation path, so this is shared upstream behavior, but
  Django Chat's `/episodes/feed/rss.xml` now routes through a local feed
  subclass that reuses django-cast's `Episode` queryset with
  `select_related("podcast_audio__transcript")` and renders the feed body from
  repository context for the episode-only catalog.
- The self-hosted podcast RSS feed is now surfaced at `/episodes/feed/` and in
  page-head RSS auto-discovery.
- Voxhelm-generated transcript handling is verified for an imported,
  non-preview episode: `/episodes/django-tasks-jake-howard/` links to its
  transcript route, `/episodes/django-tasks-jake-howard/transcript/` returns the
  themed transcript page, and the Podlove API payload includes transcript
  segments for the attached audio. No repo-side runtime fix was required for
  that staging episode; inspection showed transcript id 2 attached to audio id 1
  with Podlove JSON, WebVTT, and DOTe artifacts.

## Open Work (Highest Signal First)

1. **Custom player transcript/share parity — implemented and cut over.**
   The focused polish slice landed. Player cutover (2026-06-11): staging
   serves the custom player, and the Podlove player path was then removed
   from the repo entirely (loader script, facade markup/CSS, theme settings,
   template-proxy endpoint, deploy toggle); `CAST_AUDIO_PLAYER` is pinned to
   `"custom"` in base settings for all environments. Reverting to Podlove
   would mean reverting the removal commit, not flipping a setting. Generic
   behavior went upstream into
   django-cast and Django Chat bumped its pinned rev:
   - Upstream (django-cast): sparse timestamps in labelled transcripts (a muted
     time anchor only at speaker-run starts; continuation lines keep click-to-seek
     but hide the timestamp), a loading spinner with `aria-busy`, a restrained
     spring reveal/collapse that honors `prefers-reduced-motion`, the `Tab cues`
     control demoted to an icon-only secondary toggle (accessible name +
     `cast-transcript-tabbable` preserved), and a `data-share="none"`
     transport-share opt-out (`cast_custom_player ... transport_share=False`).
     Speaker-label sanitization is unchanged and now regression-tested through
     `AudioPlayerTranscriptView`. Covered by vitest + pytest.
   - Django Chat: opts out of the in-transport share button so the sidebar rail
     is the only share control; the full-width hairline directly below the player
     is replaced by a grid-aligned separator on `.episode-hero-content` (spans the
     content column, inset past the episode-number column); a repository-backed
     browser fixture (`diarized_custom_player_site`) creates a diarized transcript
     with matching visible contributors (and one stripped non-contributor) so the
     custom-player browser tests prove speaker headings, sparse timestamps, one
     share control, the loading busy state, and `?t=21` site sharing without
     relying on mutable dev-DB state.
   Host-review follow-ups (2026-06-08): reproducible diarized demo data via
   `just manage seed_django_chat_diarized_demo` (assigns the three visible
   contributors and writes deterministic block speaker labels onto the
   `django-tasks-jake-howard` cues; run it with staging media to seed the S3
   transcript that `just dev` reads); a dev-only `DisableTranscriptCacheMiddleware`
   (local settings) that drops the endpoint's 1-hour browser cache so seeded
   changes show on the next load; the transcript toggle restyled as a compact
   borderless panel header (not a pill) with the player pulled up under the
   headline; the separator rendered short + cover-aligned when closed and
   full-width over Hosts and Guests when open; the open transcript flattened to
   read as inline page content; and an upstream django-cast fix making the player
   focusable so the transport keyboard shortcuts (Space/K/arrows) are reachable.
   Transcript beauty/UX review follow-ups (2026-06-11, upstream django-cast
   `1ad2748e`): diarized transcripts render a heading row per speaker run (an
   initial chip echoing the Hosts-and-Guests chips, the name, and the run's
   timestamp; speakerless runs get a time-only anchor) and the per-cue gutter
   collapses; the current-cue highlight drops the per-line underline band (it
   painted past the end of each line and read as a glitch) for a single accent
   border + tint idiom; follow-along keeps look-ahead via `scroll-margin`
   instead of pinning the active line to the panel's bottom edge; far jumps
   (search/chapter) land instantly instead of smooth-scrolling for seconds;
   searching suspends follow (dimmed toggle, Escape clears and re-anchors);
   speaker comparison is trimmed and labelled cue buttons carry a
   visually-hidden speaker prefix for screen-reader focus context.
   Dev caveat: Django's `runserver` serves media without HTTP `Range` support,
   so Chromium reports the audio unseekable locally — scrubbing and `?t=`
   deep-links silently no-op under `just dev`. Production serving (nginx/S3)
   supports ranges and is unaffected; test share-with-timestamp against staging.
   Spec:
   [`docs/custom-player-transcript-share-spec.md`](custom-player-transcript-share-spec.md).
2. **Host review of staging.** With full catalog + RSS-discovery +
   Voxhelm transcript handling + Lighthouse/Web Vitals readiness + documented
   production migration risks + pre-review UI polish in place, the staging site
   is ready for host review. Send hosts the URL + `host-review-admin`
   credential.
3. **Episode tags/taxonomy import decision.** Decide whether source keywords
   should also become Wagtail/taggit episode tags. Do not blindly mirror generic
   RSS keywords into public tags without a UI/editor use case and a preservation
   policy for manual Wagtail tags; if implemented later, prefer a filtered
   source-managed tag strategy that does not wipe editor-curated tags.
4. **Manual Wagtail episode numbering workflow.** Research is captured in
   [`docs/episode-numbering-research.md`](episode-numbering-research.md).
   Canonical podcast publishing metadata now lives upstream on `cast.Episode`
   and imported episodes are backfilled during import. Upstream django-cast now
   provides opt-in first-publish numbering, and the Django Chat importer enables
   and seeds it for imported podcasts while preserving a later operator disable.
   Remaining workflow polish is operational: deploy/re-import on staging, verify
   host-created blank full episodes publish with the expected next number, and
   decide whether editors need a pre-publish suggested-number display in
   addition to publish-time assignment.
5. **Live feed parity checker.** Add a command/script that compares the current
   Simplecast feed (`https://feeds.simplecast.com/WpQaX_cs`) with a candidate
   generated or S3/CDN-served Django Chat podcast feed. It should fail on item
   count, missing/extra GUIDs, GUID order, publication-date, title, enclosure
   type, latest-episode, and copied-media byte-size regressions, with explicit
   warnings for approved differences such as moved enclosure URLs or equivalent
   duration formatting.
6. **Performance optimization backlog.** Continue tracking concrete Lighthouse
   and browser-network follow-ups in
   [`docs/lighthouse-performance.md#performance-optimization-backlog`](lighthouse-performance.md#performance-optimization-backlog).
   The HTML-discoverable `/episodes/` hero background has been verified on
   staging, and first-party CSS minification now runs during `collectstatic`.
   The view-transition JavaScript defer was reverted on 2026-06-11: the script
   must stay a classic parser-blocking head script so its `pagereveal` listener
   is registered before the first rendering opportunity (deferred, it lost that
   race on staging and broke the detail-to-overview transition and scroll
   restore). Remaining choices are whether to split or critical-inline CSS and
   whether the render-blocking `rel="expect"` hints should stay.
7. **Production VPS, DNS cutover, URL redirects, podcast directory
   updates** — last, per user. Out of scope until host review, production
   migration notes, and the
   [`feed-cutover-analysis.md`](feed-cutover-analysis.md) plan are settled.

The import pipeline treats third-party Simplecast/RSS/staging content as
untrusted: it sanitizes imported show-note HTML, scheme-checks imported link
URLs, and SSRF-guards (scheme + connect-time IP pinning + redirect
re-validation) all outbound fetches. See
[`docs/import-security.md`](import-security.md). Deliberately-unfixed residual
findings (low/accepted) are tracked in
[`docs/security-known-issues.md`](security-known-issues.md).

## Next Action

The custom-player transcript/share parity spec
([`docs/custom-player-transcript-share-spec.md`](custom-player-transcript-share-spec.md))
is implemented and verified (vitest, pytest, fixture-backed
browser tests, and a Playwright desktop/mobile pass on
`/episodes/django-tasks-jake-howard/`). Staging was cut over to the custom
player and the Podlove player path has been removed from the repo
(2026-06-11); a fresh staging Lighthouse pass against the custom player
scored 99-100 across all categories. Proceed to host review from the current
staging (custom player) baseline. The
latest-entries feed mitigation and Lighthouse/Web Vitals fixes have been
deployed, a 2026-06-02 staging RSS probe confirms both RSS routes return 205
items, and the host-review public pages scored 98-100 in final mobile and
desktop Lighthouse runs. The pre-review cleanup added
production migration notes, pagination focus/scroll behavior, episode filter
styling including custom date/select popovers, Wagtail 7.4, and an editable
Wagtail `SponsorPage` at
`/episodes/sponsor/` that replaces the upstream Google-Doc "Sponsor Us" link
with an on-site pitch (stats, sponsorship slots, pricing, hosts bio, reviews
reel, bundled PDF download). The page is a `max_count=1` singleton under the
site root, surfaced via a thin proxy view so the URL stays parallel to
`/episodes/feed/`; the menu link override in `base.html` swaps the imported
Google-Doc URL for the internal route without touching the imported source
fixture.

Production migration (DNS, feed cutover, real production VPS) is
explicitly deferred until host review (item 1) has happened and the production
feed/DNS plan is settled.
