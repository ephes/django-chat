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
      URL compatibility** — `d24968b`. Visual polish is a candidate scope
      expansion (see Next Action).
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
      episodes, CloudFront-served MP3s, `<audio>` element on detail pages).
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

## Open Work (Highest Signal First)

1. **Visual polish pass** (extends slice 6). User-flagged as priority before
   host review. No spec gap, but the current templates are minimal: plain
   "DC" badge for the logo, no per-episode artwork, palette has a green
   brand-mark next to red eyebrow text, no favicon/OG tags, no typography
   refinement. Brainstorm intent before touching templates so the work has a
   target.
2. **Transcript demo** — implement `/episodes/<slug>/transcript` for at
   least one representative episode. The PRD permits either simple page
   content or the `cast_transcripts` worker path; simple page content is the
   lower-cost route for closing this acceptance criterion.
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

Visual polish on the staging templates. The next agent should:

- Run a short brainstorm on what "looks off" means concretely — palette,
  hierarchy, logo, episode artwork, hero balance — so the design pass has a
  target rather than drifting.
- Treat this as a deliberate scope expansion of slice 6, not a new slice.
- Keep the public URL shape unchanged.
- Keep the transcript demo, full-catalog import, and
  `docs/production-migration-notes.md` as follow-ups (in that order).

**Done when** staging screenshots show a coherent Django Chat identity, show
artwork is used intentionally, favicon and basic page metadata are present
or explicitly deferred with a reason, and URL/content behavior is
unchanged.

Production migration (DNS, feed cutover, real production VPS) is explicitly
deferred until staging looks good to the hosts.
