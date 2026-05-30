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
      declares a light theme so browser dark-mode preferences do not add a
      dark iframe strip below the compact controls. Facade mode remains
      disabled.
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
- [ ] **10. Decide whether production migration needs a separate follow-up
      PRD after host review.** Decision item, not implementation; revisit after
      hosts have reviewed staging.

## Acceptance Criteria

PRD section "Acceptance Criteria For The Research Spike".

- [x] Staging site exists and loads over HTTPS.
- [x] Hosts can log into Wagtail admin (`host-review-admin` bootstrap account
      on staging).
- [x] Representative episode audio playback proven. Initially verified against
      the 8/8 copied sample; staging now has the full live catalog copied
      (202/202 live episodes with audio), CloudFront-served MP3s, and Podlove
      `<podlove-player>` elements on detail pages with django-vite-loaded init
      module.
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

Slice 6 visual polish + the post-deploy fixes that surfaced during
staging review are landed on `main` in the series ending at `f132b76`
on `2026-04-26`. The full-catalog importer slice is in the current worktree.
Staging at `https://djangochat.staging.django-cast.com` is deployed and
serving the polished site:

- Black header with show artwork mark, single-column episode rows,
  Roboto type stack self-hosted, filterset search/date facets/ordering,
  branded error pages, favicon trio, OG/Twitter metadata.
- Compact Podlove player on episode detail (no facade), themed with the
  Django-green brand tokens via `CAST_PODLOVE_PLAYER_THEMES` and a local
  `data-template` endpoint. The compact template keeps the transcript tab
  available; the transcript tab uses Podlove's transcript-results list as the
  only vertical scroller, avoiding a redundant outer panel scrollbar, while
  non-transcript tabs retain a 420px internal panel cap. Episodes with an
  attached django-cast `Transcript` expose transcript data through the Podlove
  API and link to the themed transcript route.
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

Branch is unpushed at the time of writing.

**Ready for full host review:**

The deployed staging site remains useful for internal smoke review of
deployment, CMS access, playback, the visual direction, and the full catalog.
It now has representative catalog/audio/feed state, Voxhelm-generated
transcript demos, documented production migration risks, pagination behavior
that returns reviewers to the refreshed episode results, and a polished
episode filter/search strip.

As of 2026-04-29, staging has the full live catalog copied for host-review
audio validation: `measure_django_chat_catalog
--host=djangochat.staging.django-cast.com` reports `live_episodes=202`,
`with_audio=202`, and `missing_audio=0`. Both generated RSS routes return 200
with 202 items.

- After each deploy or destructive staging refresh, re-check whether staging
  still holds the intended full live catalog/audio state.
- Lighthouse / Web Vitals readiness is cleared for the public host-review
  surfaces on deployed staging. The 2026-04-29 Lighthouse run measured `/`,
  `/episodes/`, `/episodes/django-tasks-jake-howard/`, and `/episodes/feed/`
  in both mobile and desktop modes with final scores of 98-100 across
  Performance, Accessibility, Best Practices, and SEO. See
  `docs/lighthouse-performance.md` for commands, artifact paths, before/after
  scores, and the remaining Podlove unused-CSS/JS caveat.
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

1. **Host review of staging.** With full catalog + RSS-discovery +
   Voxhelm transcript handling + Lighthouse/Web Vitals readiness + documented
   production migration risks + pre-review UI polish in place, the staging site
   is ready for host review. Send hosts the URL + `host-review-admin`
   credential.
2. **Transcript detail page design.** Addressed during the contributors +
   diarization slice (9h): the `/episodes/<slug>/transcript/` page reuses the
   episode-detail grid/sidebar, renders bold speaker names + green mono
   timestamps per segment, and keeps a "Back to Show Notes" link. Verified
   readable on staging via Playwright for `breaking-django`. Re-check mobile
   spacing if the segment list grows much longer.
3. **Episode tags/taxonomy import decision.** Decide whether source keywords
   should also become Wagtail/taggit episode tags. Do not blindly mirror generic
   RSS keywords into public tags without a UI/editor use case and a preservation
   policy for manual Wagtail tags; if implemented later, prefer a filtered
   source-managed tag strategy that does not wipe editor-curated tags.
4. **Live feed parity checker.** Add a command/script that compares the current
   Simplecast feed (`https://feeds.simplecast.com/WpQaX_cs`) with a candidate
   generated or S3/CDN-served Django Chat podcast feed. It should fail on item
   count, missing/extra GUIDs, GUID order, publication-date, title, enclosure
   type, latest-episode, and copied-media byte-size regressions, with explicit
   warnings for approved differences such as moved enclosure URLs or equivalent
   duration formatting.
5. **Performance optimization backlog.** Continue tracking concrete Lighthouse
   and browser-network follow-ups in
   [`docs/lighthouse-performance.md#performance-optimization-backlog`](lighthouse-performance.md#performance-optimization-backlog).
   The HTML-discoverable `/episodes/` hero background has been verified on
   staging. The current focus is deciding whether to defer view-transition
   JavaScript, split or critical-inline CSS, and revisit render-blocking
   `rel="expect"` hints. First-party CSS minification now runs during
   `collectstatic`.
6. **Production VPS, DNS cutover, URL redirects, podcast directory
   updates** — last, per user. Out of scope until host review, production
   migration notes, and the
   [`feed-cutover-analysis.md`](feed-cutover-analysis.md) plan are settled.

## Next Action

Proceed to host review after deploying the current pre-review cleanup. The
latest-entries feed mitigation and Lighthouse/Web Vitals fixes have been
deployed, staging catalog measurement confirms both RSS routes still return
202 items, and the host-review public pages scored 98-100 in final mobile and
desktop Lighthouse runs. The current cleanup adds production migration notes,
pagination focus/scroll behavior, episode filter styling including custom
date/select popovers, Wagtail 7.4, and an editable Wagtail `SponsorPage` at
`/episodes/sponsor/` that replaces the upstream Google-Doc "Sponsor Us" link
with an on-site pitch (stats, sponsorship slots, pricing, hosts bio, reviews
reel, bundled PDF download). The page is a `max_count=1` singleton under the
site root, surfaced via a thin proxy view so the URL stays parallel to
`/episodes/feed/`; the menu link override in `base.html` swaps the imported
Google-Doc URL for the internal route without touching the imported source
fixture.

Production migration (DNS, feed cutover, real production VPS) is
explicitly deferred until host review (item 1) has happened and any
perf fixes from the catalog measurement have landed.
