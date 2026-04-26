# Staging Differences

This document explains how Django Chat staging differs from the current
Simplecast-hosted public experience and from a future production migration.

## Current Staging Status

Staging is live at `https://djangochat.staging.django-cast.com`.

Current live state:

- `/` redirects to `/episodes/`.
- The fixture-backed sample has been imported with one podcast and eight
  episodes.
- Wagtail admin is available at
  `https://djangochat.staging.django-cast.com/cms/`.
- A staging-only `host-review-admin` superuser exists for bootstrap access.
- Sample audio has been copied to the configured S3 bucket and is served
  through the public media host. All eight episodes have `podcast_audio` set
  and episode detail pages render the django-cast **Podlove web player**
  (`<podlove-player>` element).
- The repo now has a repeatable live full-catalog import command, but the
  deployed staging database should be checked before host handoff to confirm
  whether the sample or the full catalog is currently loaded.

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
as the podcast page's `cover_image` (a `wagtail.images.Image`), which the
Podlove player surfaces as the per-episode cover.

Expected differences from Simplecast:

- Audio URLs come from the Django Chat media host, not Simplecast.
- Simplecast player JavaScript is not used. Episode detail pages embed the
  Podlove web player (the same player python-podcast.de uses), loaded via
  `django-vite` against django-cast's prebuilt manifest.
- The heavy embed script (`cast/js/web-player/embed.5.js`, ~138 KB)
  loads on viewport intersection, keeping it off the critical render path.
- Simplecast analytics, dynamic ad insertion, and Simplecast download tracking
  are not reproduced.
- Browser playback behavior may differ because the player comes from the
  self-hosted Django/django-cast stack.

## Feed Status

The staging feed is not canonical and must not be submitted to podcast
directories or redirected from Simplecast.

The feed check is a smoke-level comparison for the fixture-backed sample with
copied audio in place:

```sh
just compare-feed
```

That check validates important sample fields. Production hardening still needs
full-catalog validation, GUID and enclosure decisions, artwork and namespace
checks, client testing, and host approval before any live feed change.

## Content Import Scope

The current staging deployment contains the fixture-backed sample import for
internal smoke review unless an operator has run the live catalog command on
the host. The representative host-review deployment should use:

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
- It does not publish converted transcripts by default.
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
transcript publishing and conversion are not enabled in the default staging
deployment. The `cast_transcripts` database worker remains disabled unless a
later staging decision explicitly enables transcript publishing or conversion
jobs.

## Production Migration Boundary

Staging does not mean production migration is complete.

This slice does not:

- change the canonical Django Chat DNS records
- redirect the Simplecast feed
- update Apple Podcasts, Spotify, Pocket Casts, or other directories
- replace Simplecast analytics
- decide long-term media CDN or analytics strategy
- perform full-catalog feed parity hardening
- create production cutover instructions

Those decisions require host review and a separate production migration plan.
