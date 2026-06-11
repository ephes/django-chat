# Staging Differences

This document explains how Django Chat staging differs from the current
Simplecast-hosted public experience and from a future production migration.

## Current Staging Status

Staging is live at `https://djangochat.staging.django-cast.com`.

Current live state:

- `/` redirects to `/episodes/`.
- The full public catalog has been imported under the `episodes` podcast.
- Wagtail admin is available at
  `https://djangochat.staging.django-cast.com/cms/`.
- A staging-only `host-review-admin` superuser exists for bootstrap access.
- Full-catalog audio has been copied to the configured S3 bucket and is served
  through the public media host. All live imported episodes have
  `podcast_audio` set and episode detail pages render the django-cast
  **custom audio player** (`<cast-audio-player>` element).
- `/episodes/preview/transcript/` demonstrates a Voxhelm-generated
  django-cast transcript for the preview episode.
- The deployed staging database should still be measured before host handoff
  to confirm counts and endpoint health.

## Site And Visual Theme

The staging site uses Django, Wagtail, django-cast, and Django Chat-specific
templates. It is not a copy of the Simplecast web application.

Expected differences:

- The root URL redirects into the self-hosted episode experience.
- `/episodes/` is the episode index.
- `/episodes/<slug>/` is the episode detail URL shape preserved for imported
  sample episodes.
- Branding, layout, typography, and navigation are implemented in this app and
  may differ from Simplecast.
- Menu, social, and distribution links come from the imported fixture-backed
  Simplecast metadata in the current sample path.

Visual parity with Simplecast is a full host-review decision, not a production
migration requirement already settled by this slice.

## Player And Media Behavior

Staging is intended to prove Django Chat-specific media hosting. Media must use
a Django Chat-specific S3-compatible bucket and public media host. Do not reuse
Python Podcast media buckets, credentials, hostnames, or deployment details.

The deployed `import_django_chat_sample --copy-audio --copy-cover-image`
command has been run against production settings on the staging host.
Sample MP3s are stored in the Django Chat staging bucket and reachable
through the public media host with HTTP 200 and `Content-Type: audio/mpeg`,
providing an end-to-end playback proof. The show artwork has been attached
as the podcast page's `cover_image` (a `wagtail.images.Image`). The player
does not display a large cover slot, and episode detail
heroes render the static Django Chat SVG logo. The imported raster artwork
still feeds django-cast metadata, feed, and player API image data.
Project-level social image tags use `PodcastSourceMetadata.image_url` when
available, not this Wagtail `cover_image`.

Expected differences from Simplecast:

- Audio URLs come from the Django Chat media host, not Simplecast.
- Simplecast player JavaScript is not used. Episode detail pages render
  django-cast's custom audio player (`<cast-audio-player>`), loaded via
  `django-vite` against django-cast's prebuilt manifest and themed through
  the `--cast-player-*` token API. The transport is server-rendered, so no
  third-party player iframe or heavy embed script is involved.
- Simplecast analytics, dynamic ad insertion, and Simplecast download tracking
  are not reproduced.
- Browser playback behavior may differ because the player comes from the
  self-hosted Django/django-cast stack.

## Feed Status

The staging feed is not canonical and must not be submitted to podcast
directories. The production feed cutover plan is tracked separately in
[`feed-cutover-analysis.md`](feed-cutover-analysis.md); it assumes Simplecast
will not redirect the old feed URL.

The feed check remains a local smoke-level comparison for the fixture-backed
sample with copied audio in place:

```sh
just compare-feed
```

That check validates important sample fields. Production hardening still needs
GUID and enclosure decisions, artwork and namespace checks, client testing,
and host approval before any live feed change.

## Content Import Scope

The current staging deployment contains the live catalog import. The
representative host-review deployment should be refreshed with:

```sh
DJANGO_SETTINGS_MODULE=config.settings.production \
  .venv/bin/python manage.py import_django_chat_catalog --copy-cover-image
```

and, when the media transfer is intentionally approved:

```sh
DJANGO_SETTINGS_MODULE=config.settings.production \
  .venv/bin/python manage.py import_django_chat_catalog --copy-cover-image --copy-audio
```

Current import boundaries:

- The sample command imports a representative fixture-backed subset.
- The catalog command imports the live public RSS catalog and Simplecast
  enrichment data when the public endpoints expose it.
- It records source URLs, GUIDs, Simplecast IDs, slugs, source audio URLs, and
  transcript HTML metadata for idempotent re-runs.
- Catalog audio copy is optional, streams through a temporary file, and should
  not be run casually because the full transfer was observed at about 11 GB.
- It does not convert Simplecast transcript HTML. Existing django-cast
  transcript artifacts can be copied from staging with
  `just import-staging-transcripts`.
- It does not add large live RSS fixtures, real MP3 fixtures, or live network
  tests to the repository.

## Wagtail Admin

When the host-review gate opens, staging review uses Wagtail admin at:

```text
https://djangochat.staging.django-cast.com/cms/
```

Wagtail admin accounts are created after deployment using approved host account
details. Passwords and password-reset handoff must happen outside this repo.
The initial staging bootstrap account is `host-review-admin`; its generated
temporary credential is stored only on the staging host for secure handoff and
must be rotated or replaced after review access is settled.

The public account, comment, Fediverse proxy, and API flows from Python Podcast
are not part of the Django Chat staging scaffold.

## Transcripts

Simplecast transcript HTML is preserved in source metadata where available, but
it is not used for public transcript rendering. Staging enables the
`cast_transcripts` database worker so Wagtail can queue Voxhelm transcript generation
for individual reviewed episodes. Environments can copy the
resulting django-cast artifacts from staging with
`just import-staging-transcripts`.

In Wagtail admin, edit an episode page and use the **Generate transcript** page
action to request another transcript. The action requires editable episode and
audio permissions, copied podcast audio, and the active
`django-chat-db-worker.service` worker. The deployed Django/Wagtail host must
also be able to reach the Tailscale network where the Voxhelm API is exposed.

## Production Migration Boundary

Staging does not mean production migration is complete.

This slice does not:

- change the canonical Django Chat DNS records
- publish the production podcast feed URL
- update Apple Podcasts, Spotify, Pocket Casts, or other directories
- replace Simplecast analytics
- decide long-term media CDN or analytics strategy
- perform full-catalog feed parity hardening
- create production cutover instructions

Those decisions require host review and a separate production migration plan.
The current migration questions, feed continuity risks, media decisions, and
pre-cutover checklist are tracked in
[`docs/production-migration-notes.md`](production-migration-notes.md).
