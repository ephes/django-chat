# Host Review Guide

This guide defines the Django Chat staging review workflow for hosts. It is a
workflow reference; `docs/implementation-status.md` is the current source of
truth for whether staging is ready to send to hosts.

## Current Staging Status

Staging is live as of 2026-04-25 at:

```text
https://djangochat.staging.django-cast.com
```

Verified live behavior:

- `/` redirects to `/episodes/`.
- `/episodes/` returns the fixture-backed episode index.
- `/episodes/django-tasks-jake-howard/` returns an episode detail page.
- `/cms/` redirects anonymous visitors to the Wagtail login.
- The deployed database contains one podcast and eight sample episodes.
- A staging-only `host-review-admin` superuser exists for review bootstrap.

Sample audio is copied to the staging media bucket and served through the
public media host. Episode detail pages render the **Podlove web player**
(`<podlove-player>`) — a styled player from django-cast loaded via
`django-vite`. The heavy embed script (`cast/js/web-player/embed.5.js`,
~138 KB) loads on viewport intersection, keeping it out of the critical
render path. The MP3 URL responds with HTTP 200 and `audio/mpeg`. Sample
audio playback is therefore available end-to-end on staging.

Current staging is suitable for internal smoke review. Full host review is
deferred until the live catalog has been imported on staging and the
RSS-discovery and transcript-demo gaps listed in
`docs/implementation-status.md` are closed.

## Review URLs

- Site: `https://djangochat.staging.django-cast.com/`
- Episode index: `https://djangochat.staging.django-cast.com/episodes/`
- Episode detail: `https://djangochat.staging.django-cast.com/episodes/<slug>/`
- Wagtail admin: `https://djangochat.staging.django-cast.com/cms/`

The repository uses `/cms/` for Wagtail admin. Django's built-in admin remains
separate at `/django-admin/` and is not the normal host review surface.

## Operator Checklist Before Host Review

Before sending or refreshing the staging URL for hosts, confirm:

- DNS for the staging FQDN points at the staging VPS.
- `deploy/inventory/hosts.yml` and `deploy/group_vars/staging.yml` still
  contain the real Django Chat staging host and FQDN.
- `.sops.yaml` contains the intended age public recipient or recipients.
- `SOPS_AGE_KEY_FILE` points to the matching private key outside this repo.
- `deploy/secrets/staging.sops.yml` exists, decrypts through SOPS/age, and
  contains only Django Chat staging secrets.
- Only operators managing the shared staging environment are SOPS recipients.
  Host reviewers do not need decrypt access just to use the repo or Wagtail
  admin.
- The staging media bucket and public media host are Django Chat-specific.
- Ansible dependencies have been installed locally with `just deploy-bootstrap`.
- `just deploy-bootstrap-target staging` has completed successfully.
- `just deploy-staging` has completed successfully after any repo-side
  deployment change.
- Migrations have run on staging.
- The intended review catalog has been imported against the deployed site,
  using the deployed environment and production settings for the relevant import
  management command.
- For sample-only internal smoke review, use
  `import_django_chat_sample --copy-audio --copy-cover-image`.
- For representative host review, use `import_django_chat_catalog` for metadata
  and `import_django_chat_catalog --copy-cover-image` for show artwork. Add
  `--max-episodes 3` only for a limited operator exercise, not for the final
  review catalog.
- Review audio has been copied against the deployed environment with production
  settings when a playback/media review is in scope. Full-catalog audio copy
  uses `import_django_chat_catalog --copy-cover-image --copy-audio` and can
  transfer about 11 GB, so run it only when intentionally approved.
- The show artwork has been attached as the podcast `cover_image` via
  `import_django_chat_sample --copy-cover-image` or
  `import_django_chat_catalog --copy-cover-image` (idempotent). Without this,
  the Podlove player on episode detail pages renders an empty cover slot.
- `measure_django_chat_catalog --host=djangochat.staging.django-cast.com` has
  been run after the intended catalog import, and feed/item count plus
  episode-list query/timing results have been recorded for the review handoff.
- `https://<staging-fqdn>/`, `/episodes/`, at least one episode detail page,
  and `/cms/` return expected HTTPS responses.
- Static assets load.
- An episode detail page renders a `<podlove-player>` element with
  `data-url` pointing at `/api/audios/podlove/<id>/post/<id>/` and
  `data-config` at `/api/audios/player_config/`, and the referenced MP3
  URL returns HTTP 200 with `Content-Type: audio/mpeg` through the public
  media host.
- Browser DevTools network panel shows `cast/js/web-player/embed.5.js`
  is fetched after initial page paint (on viewport intersection), not as
  part of the critical render path.

## Admin Access

Host Wagtail accounts should be created only after staging is deployed and the
host account list is approved. Use Django or Wagtail management commands on the
deployed site, or create accounts through Wagtail admin.

The initial staging account is `host-review-admin`. It was created on the
deployed site with a generated temporary password stored only in a mode-600
bootstrap handoff file on the staging host, outside the app repository and
outside repo-managed SOPS secrets. Retrieve and share that credential only
through the agreed secure channel, then rotate it in Wagtail admin or replace
the account when host review access is settled.

Do not commit, document, or print admin passwords in this repository. Do not add
human Wagtail passwords to `deploy/secrets/*.sops.yml`.

## First Review Pass

Once the full host-review gate opens, hosts should start with:

1. Open the site root and confirm it reaches the episode experience.
2. Browse `/episodes/` and confirm episode titles, dates, descriptions, show
   artwork, navigation, menu links, social links, and distribution links feel
   recognizable for Django Chat.
3. Open at least one episode detail page and review the show notes, metadata,
   audio area, and current URL shape.
4. Press play on the rendered Podlove player; pressing play streams the
   MP3 from the public media host.
5. Log into `/cms/`, inspect the podcast and sample episode pages, and try a
   harmless draft edit without publishing over reviewed content.

## Useful Feedback Categories

When reporting feedback, include the category and the page URL:

- Blocking: anything preventing login, browsing, editing, playback, or review.
- Content: title, description, episode metadata, show notes, artwork, menu,
  social, or distribution link issues.
- Design: Django Chat visual identity, readability, spacing, and differences
  from Simplecast that matter to hosts.
- Playback and media: audio player behavior, media URLs, file availability,
  loading time, or browser compatibility.
- Admin workflow: Wagtail editing, preview, publishing, account permissions,
  or confusion in the CMS.
- Migration questions: production feed, DNS, redirects, analytics, transcripts,
  podcast directories, or full-catalog import decisions.

Do not include passwords, secret URLs, SOPS output, database credentials, S3
credentials, Mailgun keys, Sentry DSNs, or age keys in feedback tickets or
repository comments.

## Known Limitations

- Current staging uses the fixture-backed sample for internal smoke review.
  Full host review is deferred until the representative catalog is imported on
  staging and the remaining RSS-discovery and transcript-demo gaps are closed.
- The staging feed is for validation only and is not the canonical Django Chat
  podcast feed.
- No production DNS, feed redirect, Simplecast migration, or podcast directory
  update has been performed.
- Simplecast analytics, distribution analytics, and any Simplecast-specific
  player behavior are not reproduced by this scaffold.
- Transcript conversion and the `cast_transcripts` database worker remain
  disabled unless transcript publishing is explicitly added for staging.
