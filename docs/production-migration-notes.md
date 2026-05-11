# Production Migration Notes

These notes define the production migration questions that must be settled
after host review and before any live DNS, feed redirect, or podcast directory
change. Staging proves the self-hosted app can serve Django Chat content; it is
not a production cutover plan by itself.

## Current Boundary

The staging site at `https://djangochat.staging.django-cast.com` is safe for
host review because it does not change:

- the canonical `djangochat.com` DNS records
- the current Simplecast podcast feed
- Apple Podcasts, Spotify, Pocket Casts, or other directory listings
- the public Simplecast episode URLs
- Simplecast analytics, CDN behavior, or ad insertion

Do not redirect the Simplecast feed, submit the staging feed to directories, or
publish production cutover instructions until the decisions below are resolved.

## Host Decisions

Before production migration, hosts need to decide:

- whether `djangochat.com` remains the canonical site domain
- whether the podcast feed moves from Simplecast to django-cast
- whether Simplecast should redirect the old feed to the new feed
- whether old episode URLs must be preserved exactly, redirected, or allowed to
  change
- whether audio download URLs should be served directly from S3/CloudFront or
  through another CDN, analytics, or download-tracking layer
- whether Simplecast analytics, distribution analytics, or dynamic ad insertion
  is still required
- whether transcripts are owned/exportable and intended to be published on the
  self-hosted site
- whether sponsor handling is only baked into audio/show notes or depends on
  dynamic ad features

## Feed Continuity

Podcast clients are sensitive to feed identity. A production migration must
prove, with the live catalog loaded, that:

- the django-cast podcast feed validates
- existing item GUIDs are preserved for migrated episodes
- titles, publication dates, episode numbers, durations, explicit flags, and
  enclosure metadata match Simplecast where they need to
- artwork dimensions and podcast namespace fields are acceptable to major
  clients
- any current Simplecast `itunes:new-feed-url` value is checked before using
  Simplecast to announce or redirect a feed move
- `itunes:new-feed-url` behavior is understood before enabling any redirect
- Simplecast feed redirects and podcast directory updates are coordinated with
  hosts
- Apple Podcasts, Spotify, Pocket Casts, and a generic RSS client have been
  tested against the candidate feed before cutover

GUID changes are the highest-risk feed error because podcast clients may treat
old catalog episodes as new downloads.

## Media And Analytics

The current staging media setup uses Django Chat-specific S3-compatible storage
and CloudFront. That proves isolation from Python Podcast, but production still
needs explicit decisions for:

- the final media bucket and CloudFront distribution
- whether direct CloudFront MP3 URLs are acceptable for public enclosures
- whether download analytics need to preserve Simplecast-style reporting
- whether a different CDN, redirect service, or analytics layer should sit in
  front of media
- cache invalidation and rollback behavior for feed artwork and MP3 files

## URL And Domain Cutover

Production migration must preserve known public URL expectations:

- `/` should reach the show experience
- `/episodes/` should remain the episode index
- `/episodes/<slug>/` should remain the episode detail shape
- `/episodes/<slug>/transcript/` should work when a transcript exists
- any Simplecast-only paths should either redirect intentionally or remain out
  of scope by host decision

Before DNS cutover, verify canonical URLs, Open Graph URLs, RSS
auto-discovery, Wagtail `Site` configuration, `ALLOWED_HOSTS`, CSRF trusted
origins, media URLs, and admin URLs under the production hostname.

## Rollback

The safest rollback before feed/DNS cutover is to leave Simplecast unchanged.
After any production cutover, rollback needs a written operator path covering:

- who can change DNS and Simplecast feed redirect settings
- how to disable or reverse any feed redirect
- how to return podcast directories to the previous feed if needed
- how to preserve the last known-good django-cast feed output for comparison
- how to avoid changing GUIDs or enclosure URLs during rollback

## Pre-Cutover Checklist

Run this only after hosts approve a production migration:

- import the intended full catalog in the production environment
- copy production media to the final Django Chat media backend
- run `just compare-feed` and any expanded production feed parity checks
- measure the catalog with `measure_django_chat_catalog --host=<production-host>`
- smoke-test `/`, `/episodes/`, `/episodes/feed/`, a representative episode
  page, a transcript page, and `/cms/` over HTTPS
- validate the podcast feed with the candidate production hostname
- test playback from a browser and at least one podcast client
- confirm host approval for feed redirect and directory timing
- record rollback owners and exact rollback steps
