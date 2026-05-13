# Production Migration Notes

These notes define the production migration work that must be completed after
host review and before any live DNS, feed, or podcast directory change. Staging
proves the self-hosted app can serve Django Chat content; it is not a
production cutover plan by itself.

The detailed feed-specific failure analysis, remaining tactical choices, and
proposed cutover plan live in
[`feed-cutover-analysis.md`](feed-cutover-analysis.md). Treat that document as
the planning checklist before the feed moves from Simplecast to the final
S3/CDN-served `djangochat.com` feed.

## Current Boundary

The staging site at `https://djangochat.staging.django-cast.com` is safe for
host review because it does not change:

- the canonical `djangochat.com` DNS records
- the current Simplecast podcast feed
- Apple Podcasts, Spotify, Pocket Casts, or other directory listings
- the public Simplecast episode URLs
- Simplecast analytics, CDN behavior, or ad insertion

Do not submit the staging feed to directories or publish production cutover
instructions until the feed cutover plan is implemented and verified.

## Fixed Decisions

The production migration has these fixed decisions:

- `djangochat.com` remains the canonical site domain
- the podcast feed moves from Simplecast to this repo
- the production podcast feed and media are served from S3/CDN
- Simplecast will not redirect the old feed URL
- Simplecast is retired after migration

The old feed URL is `https://feeds.simplecast.com/WpQaX_cs`. Because it is not
under `djangochat.com`, this repo cannot redirect it without Simplecast
cooperation. The replacement podcast feed must be a `djangochat.com` URL, likely
`/episodes/feed/podcast/mp3/rss.xml` or a friendly same-domain alias that points
there. `/episodes/feed/rss.xml` is the latest-entries feed, not the podcast
client feed.

Open production details:

- the exact canonical feed URL under `djangochat.com`
- whether old episode URLs must be preserved exactly or redirected to
  django-cast route shapes
- whether a non-Simplecast analytics or download-tracking layer is needed in
  front of media
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
- any current Simplecast `itunes:new-feed-url` value is checked before
  retirement
- `itunes:new-feed-url` behavior is understood before directory updates
- podcast directory updates are coordinated with hosts
- Apple Podcasts, Spotify, Pocket Casts, and a generic RSS client have been
  tested against the candidate feed before cutover

GUID changes are the highest-risk feed error because podcast clients may treat
old catalog episodes as new downloads.

## Media And Analytics

The current staging media setup uses Django Chat-specific S3-compatible storage
and CloudFront. Production feed and media distribution will use the same class
of S3/CDN-backed architecture. Production still needs explicit details for:

- the final media bucket and CloudFront distribution
- the final static RSS object path, headers, and cache/invalidation behavior
- whether direct CloudFront MP3 URLs are acceptable for public enclosures
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

The safest rollback before feed/directory cutover is to leave Simplecast
unchanged. After directory updates, rollback needs a written operator path
covering:

- who can change DNS, S3/CDN feed objects, and podcast directory settings
- how to return podcast directories to the previous feed if needed
- how to preserve the last known-good CDN-served feed output for comparison
- how to avoid changing GUIDs or enclosure URLs during rollback

## Pre-Cutover Checklist

Run this only after hosts approve a production migration:

- import the intended full catalog in the production environment
- copy production media to the final Django Chat media backend
- publish the static production RSS XML to the final S3/CDN path
- run `just compare-feed` and any expanded production feed parity checks
- measure the catalog with `measure_django_chat_catalog --host=<production-host>`
- smoke-test `/`, `/episodes/`, `/episodes/feed/`, a representative episode
  page, a transcript page, and `/cms/` over HTTPS
- validate the podcast feed with the candidate production hostname
- test playback from a browser and at least one podcast client
- confirm host approval for directory timing and Simplecast retirement timing
- record rollback owners and exact rollback steps
