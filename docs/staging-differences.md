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
- Sample audio has not been copied, so playback/media verification is pending.

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

Visual parity with Simplecast is a host review decision, not a production
migration requirement already settled by this slice.

## Player And Media Behavior

Staging is intended to prove Django Chat-specific media hosting. Media must use
a Django Chat-specific S3-compatible bucket and public media host. Do not reuse
Python Podcast media buckets, credentials, hostnames, or deployment details.

The current staging site shows metadata and episode pages, but it is not a
complete playback proof. The deployed `import_django_chat_sample --copy-audio`
command was attempted and currently fails before saving the first MP3 because
the configured app IAM user lacks S3 object permissions. Diagnostics show
`s3:PutObject` is not allowed, and S3 `HeadObject` also returns
`403 Forbidden`. After the media credential or bucket policy is corrected,
re-run the deployed command with `--copy-audio` and verify playback through the
public media host.

Expected differences from Simplecast:

- Audio URLs will come from the Django Chat media host once copied.
- Simplecast player JavaScript is not used.
- Simplecast analytics, dynamic ad insertion, and Simplecast download tracking
  are not reproduced.
- Browser playback behavior may differ because the player comes from the
  self-hosted Django/django-cast stack.

## Feed Status

The staging feed is not canonical and must not be submitted to podcast
directories or redirected from Simplecast.

The feed check is a smoke-level comparison for the fixture-backed sample after
audio has been copied:

```sh
just compare-feed
```

That check validates important sample fields, but it currently cannot be used
as a staging playback proof because copied sample audio is blocked. Production
hardening still needs full-catalog validation, GUID and enclosure decisions,
artwork and namespace checks, client testing, and host approval before any live
feed change.

## Content Import Scope

The first review deployment should contain at least the fixture-backed sample
import. A larger catalog sample or full catalog import requires an explicit
operator and host decision because it increases media transfer, storage, and
review scope.

Current sample limitations:

- It imports a representative fixture-backed subset, not the full public
  catalog.
- It currently has no copied MP3 files attached to the episode pages.
- It records source URLs, GUIDs, Simplecast IDs, slugs, source audio URLs, and
  transcript HTML metadata for idempotent re-runs.
- It does not publish converted transcripts by default.
- It does not add large live RSS fixtures, real MP3 fixtures, or live network
  tests to the repository.

## Wagtail Admin

Staging host review uses Wagtail admin at:

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
