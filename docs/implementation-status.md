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
- [ ] **10. Decide whether production migration needs a separate follow-up
      PRD after host review.** Decision item, not implementation; revisit after
      hosts have reviewed staging.

## Acceptance Criteria

PRD section "Acceptance Criteria For The Research Spike".

- [x] Staging site exists and loads over HTTPS.
- [x] Hosts can log into Wagtail admin (`host-review-admin` bootstrap account
      on staging).
- [x] Representative sample of episodes imported with audio playback (8/8
      episodes, CloudFront-served MP3s, Podlove `<podlove-player>` element
      on detail pages with django-vite-loaded init module).
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
- [ ] Full catalog import path documented and repeatable. **Partial: the
      `import_django_chat_sample` command is fixture-backed; no full-catalog
      run against the live ~201-episode feed has been done or documented as a
      repeatable workflow.**
- [x] Media storage isolated from Python Podcast (separate bucket, separate
      IAM credentials, separate CloudFront distribution).
- [x] Generated podcast feed validates for imported episodes (smoke level via
      `just compare-feed`; exhaustive parity deferred to production hardening
      per PRD).
- [ ] Remaining production migration risks documented before any live
      feed/DNS change. **`docs/production-migration-notes.md` does not exist
      yet.**

## Where We Are

Slice 6 visual polish + the post-deploy fixes that surfaced during
staging review are landed on `main` as 21 commits
(`32f1725`..`4d880f3`) on `2026-04-26`. `just check` clean (89 tests).
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
  with `TemplateBaseDirectory=django_chat`, both via the new
  `ensure_default_site` post-deploy task so fresh installs match.
- `import_django_chat_sample --copy-audio --copy-cover-image` is the
  documented operator command for a fresh staging build.

Branch is unpushed at the time of writing.

Immediate next move: hand the deployed staging URL to hosts for review.
Once feedback has settled, start the subscribe/RSS-discovery page slice
below.

## Open Work (Highest Signal First)

1. **Subscribe / RSS-discovery page** — customise django-cast's
   `feed_detail.html` (rendered at `cast:feed_detail` → `/episodes/feed/`)
   to expose the RSS feed URL prominently and embed the Podlove Subscribe
   Button. Re-target the `Listen & Subscribe` button on the show hero to
   `{% url 'cast:feed_detail' slug=podcast.slug %}` instead of
   `source_metadata.website_url` — that resolves both the RSS-promotion gap
   the slice-6 polish opened and the post-cutover self-loop risk in one
   change. Concrete sub-tasks:
   - Add `django_chat/templates/cast/django_chat/feed_detail.html`
     extending the relevant cast base; without it the route falls through
     to `cast/plain/feed_detail.html` and breaks the branded shell.
   - Decide source-of-truth for platform links: django-cast's feed view
     reads `CAST_FOLLOW_LINKS` from settings, but real distribution links
     live in `PodcastSourceMetadata.visible_distribution_links`. Pick one
     (recommended: read source_metadata in the template, ignore
     `CAST_FOLLOW_LINKS`).
   - Bring the Podlove Subscribe Button asset into the repo
     (`django_chat/static/subscribe_button/`) — the JS/CSS/icon bundle is
     not yet present. Reference layout in
     `python-podcast/python_podcast/static/subscribe_button/`. Decide
     whether to vendor it or pull it as a Python dep.
   - Keep canonical/OG metadata correct on this page (re-use `_meta.html`
     with an appropriate `og_type`).
2. **Transcript demo** — implement `/episodes/<slug>/transcript` for at
   least one representative episode. PRD permits either simple page content
   or the `cast_transcripts` worker path; simple page content is the
   lower-cost route. Defer until item 1 (and host review) has landed.
3. **`docs/production-migration-notes.md`** — feed redirect risks, GUID
   preservation, canonical domain, Simplecast directory coordination,
   analytics/CDN/ad-insertion questions. Content scope is in PRD lines
   520–525 and "Production Migration Considerations" section.
4. **Full-catalog import path** — extend the import command (or document a
   parallel command) for the live ~201-episode catalog, including audio
   transfer at ~11 GB, retry/resume behavior, and the operator runbook. PRD
   "Import Strategy" section is the contract.
5. **Production VPS, DNS cutover, feed redirects, podcast directory
   updates** — last, per user. Out of scope until the items above are
   settled and hosts have reviewed staging.

## Next Action

Hand staging to hosts for review. Sequence:

1. Push the unpushed `main` to origin (operator decision; no automation
   trigger required).
2. Send the staging URL + `host-review-admin` credential to hosts.
3. Iterate small if hosts flag anything.
4. Then item 1 (subscribe/RSS-discovery page), then 2 (transcript demo),
   then 3–5 in order.

Production migration (DNS, feed cutover, real production VPS) is explicitly
deferred until staging looks good to the hosts.
