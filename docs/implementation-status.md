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
      advertises the RSS feeds via `<link rel="alternate"
      type="application/rss+xml">` head metadata,
      renders imported platform links from
      `PodcastSourceMetadata.visible_distribution_links`, and the show hero's
      "Listen & Subscribe" CTA points there instead of the Simplecast site.
      Follow-up: the overview hero no longer duplicates Apple Podcasts as a
      secondary CTA; imported platform links remain in the overview link band
      and subscribe page.
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
- [ ] Public URL patterns `/`, `/episodes/`, `/episodes/<slug>`, and
      `/episodes/<slug>/transcript` represented or redirected. **First three
      ✓; the transcript URL shape reverses via django-cast
      (`cast:episode-transcript` → `/episodes/<slug>/transcript/`), but no
      transcript content or demo is imported, so the route returns nothing
      meaningful in practice.**
- [x] Menu, social, and distribution links from the Simplecast site
      represented.
- [ ] Transcript handling demonstrated for at least one representative
      episode (simple page content or `cast_transcripts` worker path). **Not
      implemented.**
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
- [ ] Remaining production migration risks documented before any live
      feed/DNS change. **`docs/production-migration-notes.md` does not exist
      yet.**

## Where We Are

Slice 6 visual polish + the post-deploy fixes that surfaced during
staging review are landed on `main` in the series ending at `f132b76`
on `2026-04-26`. The full-catalog importer slice is in the current worktree.
Staging at `https://djangochat.staging.django-cast.com` is deployed and
serving the polished site:

- Black header with show artwork mark, single-column episode rows,
  Roboto type stack self-hosted, filterset search/date facets/ordering,
  branded error pages, favicon trio, OG/Twitter metadata.
- Podlove player on episode detail (no facade), themed with the
  Django-green brand tokens via `CAST_PODLOVE_PLAYER_THEMES`.
- Show artwork attached to `Podcast.cover_image` so the player's cover
  slot is populated.
- Wagtail `Site` row pinned to `djangochat.staging.django-cast.com:443`
  with `TemplateBaseDirectory=django_chat`, via the new
  `ensure_default_site` post-deploy task.
- `import_django_chat_sample --copy-audio --copy-cover-image` is the
  documented operator command for a fresh staging build.
- `import_django_chat_catalog --copy-cover-image --copy-audio` is the
  documented operator command for representative full-catalog host-review
  audio state.

Branch is unpushed at the time of writing.

**Not yet ready for full host review, despite the polish, full catalog/audio
copy, and RSS-discovery page:**

The deployed staging site remains useful for internal smoke review of
deployment, CMS access, playback, the visual direction, and the full catalog.
It is not ready to hand to hosts as the representative show review because the
transcript-demo acceptance criterion is still open.

As of 2026-04-29, staging has the full live catalog copied for host-review
audio validation: `measure_django_chat_catalog
--host=djangochat.staging.django-cast.com` reports `live_episodes=202`,
`with_audio=202`, and `missing_audio=0`. Both generated RSS routes return 200
with 202 items.

- After each deploy or destructive staging refresh, re-check whether staging
  still holds the intended full live catalog/audio state.
- Lighthouse / Web Vitals scores against the old 8-episode sample are
  obsolete. Use the current full-catalog measurement for feed/item count and
  episode-list query/timing data, then run manual Lighthouse/Web Vitals checks
  on deployed staging.
- Latest-entries feed measurement on 2026-04-29 reported `queries=620` across
  202 items; investigate before host handoff in case it is an N+1.
- The self-hosted podcast RSS feed is now surfaced at `/episodes/feed/` and in
  page-head RSS auto-discovery; hosts still need transcript review before the
  site is ready for full handoff.

## Open Work (Highest Signal First)

1. **Transcript demo** — implement `/episodes/<slug>/transcript` for at
   least one representative episode. PRD permits either simple page
   content or the `cast_transcripts` worker path; simple page content is
   the lower-cost route. Closes the "transcript handling demonstrated"
   acceptance criterion.
2. **Host review of staging.** With full catalog + RSS-discovery +
   transcript demo in place, the staging site finally looks like the
   show. Send hosts the URL + `host-review-admin` credential.
3. **`docs/production-migration-notes.md`** — feed redirect risks, GUID
   preservation, canonical domain, Simplecast directory coordination,
   analytics/CDN/ad-insertion questions. Content scope is in PRD lines
   520–525 and "Production Migration Considerations" section. Required
   before any DNS or feed cutover.
4. **Production VPS, DNS cutover, feed redirects, podcast directory
   updates** — last, per user. Out of scope until 1–3 are settled.

## Next Action

Implement the **transcript demo** slice. Before host handoff, use the recorded
full-catalog measurement to decide whether the latest-entries feed query count
needs a focused performance fix before hosts review the site.

Production migration (DNS, feed cutover, real production VPS) is
explicitly deferred until host review (item 2) has happened and any
perf fixes from the catalog measurement have landed.
