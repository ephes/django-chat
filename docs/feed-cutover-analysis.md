# Feed Cutover Analysis

Date: 2026-05-13 (revised 2026-06-15: Simplecast's native 301 RSS Feed Redirect
is now the primary migration lever, reversing the original "Simplecast will not
redirect" decision; see "Key Constraint" and "Sources". Revised 2026-06-20: the
production podcast feed is generated and served dynamically by the django-cast
app at a stable `djangochat.com` route — the same way `../python-podcast` and the
current staging deploy serve it — not pre-rendered to a static S3/CDN RSS object.
S3/CDN stays media-only, for audio enclosures and artwork).

This document is the production feed migration plan for replacing the current
Simplecast-served Django Chat site/feed with output from this repository.
Staging can prove the app works, but feed cutover can affect every subscribed
listener.

## Fixed Decisions

The production migration has these known decisions:

- `djangochat.com` remains the canonical site domain.
- the podcast feed will move from Simplecast to this repo.
- the production podcast feed is generated and served by the django-cast app at
  a stable `djangochat.com` route, behind the same reverse proxy/caching as the
  rest of the site — the same shape `../python-podcast` and the current staging
  deploy use. The feed is not pre-rendered to a static object. Audio enclosures
  and show artwork are served from S3/CDN (media storage) under a Django
  Chat-controlled media hostname.
- Simplecast's native RSS Feed Redirect (301) is the primary migration lever.
  It is set on the old feed to point at the canonical `djangochat.com` feed
  before the Simplecast account is retired. (This revises the original
  2026-05-13 decision that "Simplecast will not redirect the old feed URL";
  see "Key Constraint" below for why.)
- after migration, Simplecast is retired rather than kept as a long-term
  publishing, feed, or media backend — but only after the 301 redirect is set,
  verified, and given at least a four-week transition window.
- web URL compatibility redirects in this repo are a separate concern: they
  cover `djangochat.com` page paths whose django-cast shape differs from the
  current Simplecast site, not the RSS feed redirect (which Simplecast itself
  serves).

The current Simplecast feed is:

- `https://feeds.simplecast.com/WpQaX_cs`

That URL is not under `djangochat.com`, so this repo (Django, S3, or the CDN)
cannot redirect it directly. The redirect is instead configured inside
Simplecast itself: its **RSS Feed Redirect** setting (show settings →
Distribution → Advanced Settings) issues a 301 from
`https://feeds.simplecast.com/WpQaX_cs` to the canonical `djangochat.com` feed.
Simplecast documents that this redirect activates within minutes, propagates to
directories within roughly 24 hours, and stays in place after the account is
closed — provided it is set *before* the show or account is deleted.

The final self-hosted feed URL is the django-cast podcast route under
`djangochat.com`, for example:

- `https://djangochat.com/episodes/feed/podcast/mp3/rss.xml`

That final URL can still be hidden behind a friendlier same-domain alias such
as `https://djangochat.com/feed/rss.xml`, but the actual canonical feed URL
must be chosen once and then kept stable.

Operationally, django-cast both generates and serves the podcast RSS: the app
renders the feed on request at that route, behind the same reverse proxy and
caching as the rest of the site (django-cast already sends a `cache-control`
max-age on the feed; a longer edge/proxy cache can front it if feed load ever
warrants). There is no separate step that pre-renders the RSS to a static S3/CDN
object — that is how `../python-podcast` and the current staging deploy already
work, and it keeps the generated feed the single source of truth instead of
introducing a second, separately-published copy that can drift stale. Cutover
validation therefore checks the feed URL the app serves under `djangochat.com`
(and, before that, the staging feed route), not a static object.

Important route distinction:

- `/episodes/feed/podcast/mp3/rss.xml` is the podcast-client feed.
- `/episodes/feed/rss.xml` is the latest-entries/site feed and should not be
  used as the replacement for the Simplecast podcast feed.
- A same-domain alias such as `/feed/rss.xml` may redirect to the podcast feed
  for human readability, but it cannot move clients subscribed to
  `https://feeds.simplecast.com/WpQaX_cs`.

## Key Constraint

The safest podcast-feed migration pattern is an old-feed 301 redirect plus
`itunes:new-feed-url`. Apple documents both mechanisms, Simplecast documents an
RSS Feed Redirect setting, and Spotify host-migration docs also rely on a 301:

- https://podcasters.apple.com/support/837-change-the-rss-feed-url
- https://help.simplecast.com/hc/en-us/articles/21953692033437-Can-I-move-my-RSS-feed-away-from-Simplecast
- https://support.spotify.com/am/creators/article/switching-away-from-spotify-for-creators-with-a-301-redirect/

This plan uses that pattern. Simplecast's RSS Feed Redirect makes the move
transparent for the large majority of subscribers and directories: clients that
poll `https://feeds.simplecast.com/WpQaX_cs` follow the 301 to the
`djangochat.com` feed on their next fetch. This is the industry-standard "change
of address" every competing host (Transistor, Buzzsprout, Zencastr, RSS.com)
documents as the way to leave Simplecast without losing subscribers.

Note on `itunes:new-feed-url`: Apple recommends pairing a 301 with this tag, but
the tag lives in feed XML and only helps clients that still read the old feed's
body. Once Simplecast's redirect is active the old URL returns a 301 instead of
XML, so the 301 is the operative old-feed signal. Simplecast exposes the
redirect control, not raw old-feed XML editing, so this plan sets
`itunes:new-feed-url` only in the *new* feed as a self-canonical marker and does
not assume it can be injected into the old Simplecast feed.

Two residual risks remain, and they are why directory updates and monitoring
stay in the plan rather than being dropped:

- **Ordering.** Simplecast deletes the feed (and drops the show from every
  directory) if the account is closed or the show deleted *before* the redirect
  is set. The redirect must be set first and verified, then the account kept
  open through at least a four-week transition window.
- **Long-term trust.** The redirect is served by Simplecast/SiriusXM, the host
  we are leaving. Their docs say redirects persist after account closure, but we
  do not control that infrastructure indefinitely. Directory listings are
  therefore also updated to the `djangochat.com` feed so the new feed is
  reachable on its own, independent of the Simplecast redirect continuing to
  work.

A small tail of direct RSS subscribers on clients that ignore both the 301 and
`itunes:new-feed-url` may still need to resubscribe manually, but that is a minor
residual rather than the central, unavoidable risk the original plan assumed.

## Current Observations

Observed on 2026-05-13:

- Simplecast feed returns HTTP 200, `application/xml`, `cache-control:
  max-age=3600`, and 204 items.
- Simplecast feed generator is `https://simplecast.com`.
- Simplecast feed has `atom:link rel="self"` set to
  `https://feeds.simplecast.com/WpQaX_cs`.
- Simplecast feed currently has a self-referential `itunes:new-feed-url` set to
  `https://feeds.simplecast.com/WpQaX_cs`.
- Staging feed returns HTTP 200, `application/rss+xml; charset=utf-8`,
  `cache-control: max-age=300`, and 202 items.
- Staging feed generator is `Django Web Framework / django-cast`.
- Staging feed has no `itunes:new-feed-url`.
- The 202 common staging/source item GUIDs are in the same order and use
  `isPermaLink="false"`.
- Staging is missing the two latest Simplecast episodes:
  - episode 203, `Deploy on Day One - Calvin Hendryx-Parker`, published
    2026-05-13 10:00 UTC
  - episode 202, `EuroPython 2026 - Mia Bajic`, published
    2026-05-06 10:00 UTC
- At the time of the 2026-05-13 observation, staging omitted
  `itunes:episode` values for all common items. The Django Chat importer and
  django-cast pin now support canonical episode metadata, so updated generated
  feeds should emit positive imported episode numbers after deployment/reimport;
  the preview source value `0` remains an approved omission.
- Staging formats `itunes:duration` differently for all common items
  (`1:14:01` instead of `01:14:01`, for example). This is probably harmless,
  but should be normalized or accepted explicitly in tooling.
- Six common item titles differ only by trailing whitespace.
- Seventeen common enclosure lengths differ from the Simplecast feed values.
  Enclosure URLs differ by design because staging uses copied media, but copied
  byte lengths must be checked against the actual stored objects.

Observed on 2026-06-20 (live `compare_django_chat_live_feed` run, source = live
Simplecast, candidate = staging feed):

- Both feeds now have 205 items; the 2026-05-13 202-vs-204 gap is closed. Staging
  was re-imported after that snapshot, so it carries episodes 202 and 203 and the
  later catalog growth.
- Every strict parity gate passed structurally: equal item count, identical GUID
  set and order, latest source episode present, and matching titles (after
  whitespace normalization), publication instants, durations, and enclosure
  types.
- Enclosure URLs differ for all 205 items by design — staging serves copied media
  from its own CloudFront distribution
  (`d3bhztlgsx3bsw.cloudfront.net/cast_audio/…`) rather than Simplecast/Podtrac.
  This is an approved warning, and confirms the architecture: feed served by the
  app, media on S3/CDN.
- 16 items report a source-reported-vs-copied enclosure byte-length difference —
  the approved "copied object size ≠ Simplecast-reported size" warning.
- The enclosure copied-byte-size gate is also validated, two independent ways
  across all 205 items. A CDN HEAD sweep confirmed every feed-declared enclosure
  `length` equals the actual CloudFront object `Content-Length` (type
  `audio/mpeg`), and a read-only check on the staging host confirmed every feed
  `length` equals staging's recorded `EpisodeAudioImportMetadata.copied_byte_size`
  (205/205, zero mismatches, every item has a copied-size row).

Conclusion: as of 2026-06-20 the staging feed is a verified match for the live
Simplecast feed (205 = 205; all strict parity gates pass with only approved
warnings, and enclosure byte sizes are confirmed both against the actual CDN
objects and against staging's import DB). No staging feed changes are needed; the
remaining cutover gates are off-staging (Simplecast 301 redirect access and the
production-environment work at cutover).

## Ways This Can Go Wrong

### Old Subscribers Stay On Simplecast

This was the highest migration risk under the original "no Simplecast redirect"
decision. Setting Simplecast's 301 RSS Feed Redirect demotes it to a manageable
risk: the failure modes below now describe what happens only if the redirect is
skipped, set too late (after account closure), or stops being honored.

Failure modes:

- podcast clients that subscribed directly to `https://feeds.simplecast.com/WpQaX_cs`
  keep polling it forever
- generic RSS clients never consult Apple, Spotify, Pocket Casts, or other
  directories after the initial subscription
- Simplecast continues serving the old feed with stale data, so old clients do
  not fail loudly
- Simplecast is shut down after migration, so old clients receive errors or
  stale cached data instead of the new feed
- the old feed remains self-referential through `itunes:new-feed-url`, so
  clients that support that tag are not told to move
- directories update to the new feed, but already-installed apps keep a cached
  old feed URL

Mitigation:

- set Simplecast's RSS Feed Redirect (301) on the old feed, pointing at the
  canonical `djangochat.com` feed, as the primary migration lever; set it before
  closing the account, and verify it returns a 301 to the new URL
- keep `itunes:new-feed-url` set in the new feed as a self-canonical marker (it
  cannot be injected into the old Simplecast feed, which returns a 301 once the
  redirect is active)
- keep the Simplecast account open for at least a four-week transition window after the
  redirect is set
- update every directory/dashboard that can be updated manually, as a backup
  that does not depend on the Simplecast redirect surviving long-term
- publish an announcement episode or short show-note announcement before the
  move, while the old feed is still active
- add visible subscribe/migration messaging on `djangochat.com`
- accept that a small tail of direct RSS subscribers on clients that ignore both
  the 301 and `itunes:new-feed-url` may still need to resubscribe manually

### Duplicate Old Episodes

Podcast clients use item GUIDs to decide whether an episode is new. If existing
episode GUIDs change, clients may show or download the full back catalog again.
Apple explicitly warns that changing GUIDs can cause duplicate episodes and
analytics problems.

Failure modes:

- imported episode pages generate new django-cast/Wagtail UUIDs instead of
  using the RSS GUIDs
- a future re-import recreates pages with different identifiers
- the feed omits GUIDs, making clients fall back to enclosure URLs
- `guid isPermaLink` changes semantics unexpectedly
- duplicate GUIDs appear in the feed
- old episodes are republished with new GUIDs after manual CMS edits

Mitigation:

- keep RSS GUIDs as immutable imported source data
- keep `guid isPermaLink="false"` for imported episodes
- add a production parity check that fails on missing, changed, duplicated, or
  reordered GUIDs for migrated episodes
- make the admin/publishing workflow unable to accidentally change imported
  GUIDs

### New Episodes Do Not Reach Subscribers

The opposite failure is also possible: old episodes survive, but subscribers
stop seeing new episodes.

Failure modes:

- directory updates lag behind the first self-hosted episode
- the new feed is generated from a stale import and is missing recent
  Simplecast episodes
- the new publishing workflow creates web pages but not podcast audio, and
  django-cast excludes episodes without podcast audio from podcast feeds
- cache headers, feed caching, CDN caching, or Wagtail site settings keep
  serving an old feed
- the final feed URL changes after directories have already been updated
- the final feed is reachable in a browser but blocked or malformed for podcast
  clients
- a reverse-proxy or CDN cache in front of the app keeps serving a stale feed
  after a new episode is published

Mitigation:

- do not update directories until the self-hosted production feed has the full
  live catalog and the latest known episode
- dry-run a new-episode publication on the candidate feed before cutover
- subscribe to the candidate feed in Apple Podcasts, Spotify, Pocket Casts,
  Overcast, and a plain RSS client before cutover
- plan a publishing freeze around cutover, or publish the next episode only
  after directory updates and feed health are verified
- monitor feed item count, latest GUID, latest publication date, and HTTP status
  continuously during the first week
- monitor the live `djangochat.com` feed URL as podcast clients see it (through
  any reverse-proxy/CDN cache), not only the Django origin response

### Directory Migration Splits The Audience

With the Simplecast 301 RSS Feed Redirect as the primary lever, directories are
a backup path for audience continuity, and each directory can still behave
differently.

Failure modes:

- one directory accepts the new URL while another continues polling Simplecast
- the new feed is submitted as a new show instead of updating the existing show
- listeners see duplicate Django Chat listings
- directory dashboards require host account access that is not available during
  the cutover window
- directory mirrors cache the old feed for days

Mitigation:

- inventory every current distribution link and owner account before scheduling
  cutover
- update existing listings in place; do not create replacement shows unless
  hosts intentionally want split listings
- record the old feed URL and new feed URL in each directory dashboard
- verify each directory after update using both the dashboard and the public app
- expect propagation delays and avoid publishing the first new self-hosted
  episode immediately after changing directories

### `itunes:new-feed-url` Is Wrong Or Unavailable

`itunes:new-feed-url` is an Apple/iTunes migration signal. It is useful during
feed moves, but only if the old feed or directory actually exposes the move.

Failure modes:

- the Simplecast 301 redirect is not set before cutover, so clients polling the
  old feed never see the new URL
- the new feed points `itunes:new-feed-url` at the old Simplecast feed, causing
  a loop or migration reversal
- the new feed points at a staging URL
- the new feed points at an Apple mirror URL instead of the real RSS URL
- the tag is left in a surprising state after rollback

Mitigation:

- add an explicit production setting for `itunes:new-feed-url`
- keep it absent in staging unless testing migration behavior deliberately
- set it to the final production RSS URL in the new feed during cutover
- verify the rendered XML before directory updates
- rely on the Simplecast 301 redirect to announce the move from the old feed;
  `itunes:new-feed-url` is a new-feed self-canonical marker only, because the old
  Simplecast feed returns a 301 (not XML) once the redirect is active

### Enclosures Or Media Delivery Break

GUID stability should prevent old episodes from appearing as new, but enclosure
problems can still break playback and downloads.

Failure modes:

- copied MP3 objects are incomplete, corrupted, or different from the source
- enclosure `length` does not match stored object size
- enclosure `type` is wrong
- media host does not support HEAD or byte-range requests consistently
- CloudFront/S3 permissions, cache behavior, TLS, or CORS changes block player
  or client downloads
- an episode is published (so it appears in the generated feed) before its
  referenced MP3/artwork objects are available on S3/CDN
- the served feed has the wrong `Content-Type`, compression, or cache headers
- signed or expiring URLs are accidentally used in RSS
- Podtrac/Simplecast analytics redirects are removed without host approval
- dynamic ad insertion or ad-marker behavior changes

Mitigation:

- compare generated enclosure length to actual stored object byte size
- sample-download and hash representative MP3 files
- test HTTP HEAD and range requests against production media URLs
- keep feed enclosure URLs public, stable, HTTPS, and non-expiring
- upload media objects to S3/CDN before publishing an episode that references
  them in the feed
- verify response headers for the served feed URL and the S3/CDN artwork and
  MP3 URLs
- get host approval on the analytics/ad-insertion tradeoff before replacing
  Simplecast/PODTRAC URLs with direct CloudFront URLs

### Metadata Or Directory Validation Regresses

Even if GUIDs and enclosures are right, directories can reject or degrade a feed
when show metadata changes.

Failure modes:

- show artwork URL, dimensions, MIME type, or cache behavior changes
- required iTunes fields are missing or malformed
- category, explicit flag, author, owner email, language, or copyright changes
- episode type, season, or positive episode number tags disappear
- descriptions are escaped differently or contain unsupported markup
- feed item count is capped unexpectedly
- channel link, canonical site URL, and feed auto-discovery disagree

Mitigation:

- validate the exact production feed URL in Apple Podcasts Connect before
  directory update
- compare show-level fields and item-level fields against Simplecast
- preserve positive `itunes:episode` values from canonical episode metadata and
  keep the preview source value `0` as an explicit approved omission
- keep old and new feeds available for diffing during the whole cutover window

### Web URL Redirects Are Missing Or Wrong

The requested redirects are for site URL compatibility. The current public
surface includes `/`, `/episodes`, `/episodes/<slug>`, and
`/episodes/<slug>/transcript`; django-cast may prefer trailing slashes and
deeper feed paths.

Failure modes:

- `https://djangochat.com/episodes/<slug>` returns 404 instead of redirecting
  to the django-cast page
- transcript URLs differ by trailing slash or route shape
- `/episodes` and `/episodes/` behave differently
- page-head canonical URLs point to staging or to an internal django-cast path
- old Simplecast-only paths are accidentally treated as valid because the old
  Simplecast app returned HTTP 200 for arbitrary paths
- feed discovery links point to the wrong final feed URL

Mitigation:

- preserve current known public page URLs directly where possible
- add explicit permanent redirects for trailing-slash and route-shape
  differences
- avoid broad catch-all redirects from arbitrary Simplecast paths
- verify canonical URLs, Open Graph URLs, RSS auto-discovery, Wagtail `Site`,
  `ALLOWED_HOSTS`, CSRF trusted origins, media URLs, and admin URLs under
  `djangochat.com`
- keep the final feed URL and any friendly feed alias on `djangochat.com`

### Rollback Is Hard After Directories Move

Before directory updates, rollback is easy: leave Simplecast as the effective
feed. After directory updates, some clients and directories will have learned
the new feed URL.

Failure modes:

- switching directories back does not bring all clients back
- clients that migrated to the new URL keep polling it
- the new production feed URL disappears during rollback
- a rollback changes GUIDs or enclosure URLs again, creating a second wave of
  duplicate/missing episodes
- setting the Simplecast 301 redirect deactivates the old feed for new
  publishing, so once the redirect is set, returning to Simplecast as the active
  host is no longer a simple rollback option

Mitigation:

- after directory updates, prefer "fix forward" by repairing the new feed URL
- keep the new feed URL online even if the website is rolled back
- save a last-known-good copy of both old and new feeds before cutover
- write exact rollback owners and commands before cutover

## Remaining Tactical Choices

The main migration shape: a Simplecast 301 RSS Feed Redirect to the app-served
`djangochat.com` feed, backed by directory updates, with Simplecast retired
after a transition window. The remaining choices are tactical.

### Final Feed URL Shape

The canonical feed can either be the django-cast route path or a friendlier
same-domain alias.

Recommendation:

- keep `https://djangochat.com/episodes/feed/podcast/mp3/rss.xml` as the
  generated route
- expose `https://djangochat.com/feed/rss.xml` as an optional permanent alias
  if hosts want a simpler public URL
- do not use `https://djangochat.com/episodes/feed/rss.xml` as the canonical
  replacement feed because that route is the latest-entries feed
- choose one URL as canonical in directory dashboards and
  `itunes:new-feed-url`

### Feed Serving And Media Publishing

The feed is generated and served by django-cast at its `djangochat.com` route;
it is not pre-rendered to a static object. Media (audio enclosures, artwork) is
published to S3/CDN exactly as it already is on staging.

Required behavior:

- upload referenced media/artwork objects to S3/CDN before publishing an episode
  that makes them appear in the feed
- serve the feed with a correct `Content-Type` and a sensible `cache-control`;
  if feed load ever warrants, cache it at the reverse proxy/CDN edge rather than
  pre-publishing a static copy
- keep a last-known-good capture of both the old and new feed XML before cutover
  for rollback comparison (a saved response body, not a published object)

### Communication Window

Even with the Simplecast 301 redirect as the primary migration lever,
communication is part of the technical plan, not a nice-to-have.

Choices:

- announce the new feed before the final Simplecast-hosted episode
- publish a short migration notice episode before shutdown
- place a visible migration/subscription notice on `djangochat.com`
- keep any short Simplecast transition window strictly time-boxed before final
  retirement

The unavoidable residual risk is that some old direct-feed subscribers still
will not move.

## Proposed Plan

### Phase 1: Choose The Final Feed URL

Pick the final canonical feed URL before any directory update.

Recommendation:

- generated route:
  `https://djangochat.com/episodes/feed/podcast/mp3/rss.xml`
- optional friendly canonical URL:
  `https://djangochat.com/feed/rss.xml`

The chosen canonical URL must be the exact app-served `djangochat.com` URL that
directories and podcast clients fetch. Once directories are updated, do not
change it again.

### Phase 2: Build Strict Live Feed Parity

Add or extend tooling so production hardening compares the live Simplecast feed
against a candidate self-hosted feed, not only committed sample fixtures.

Hard failures:

- source item count does not match candidate item count
- any source GUID is missing from the candidate feed
- any candidate GUID is not present in the source feed before cutover
- common GUID order differs
- common title differs after agreed normalization
- publication instant differs
- enclosure type is missing or unexpected
- generated enclosure length differs from actual copied object size
- latest source episode is missing from candidate feed

Warnings or explicit approvals:

- enclosure URLs differ because media has moved
- RSS-reported Simplecast enclosure length differs from copied object size
- duration formatting differs but parses to the same number of seconds
- description HTML differs but renders acceptably
- show-level metadata differs by host decision

These gates are implemented by the `compare_django_chat_live_feed` management
command (`just compare-live-feed --candidate-url <url>`; `--source-url` defaults
to the live Simplecast feed, `--timeout` to 30s). It fetches both feeds through
the import SSRF guard (`safe_urlopen` — scheme check, connect-time IP pinning,
redirect re-validation), parses the live Simplecast RSS and the candidate feed,
and runs the shared feed comparator
(`compare_source_to_generated_feed(..., strict_live_parity=True)`). It enforces
every hard failure above and keeps every approved difference a warning. The
candidate enclosure byte-size truth is the copied object size recorded in the
local import DB (`EpisodeAudioImportMetadata.copied_byte_size`), not the
source-reported RSS length. The command prints a PASS/FAIL report and exits
non-zero on any failure, so it can gate the Phase 4 dry run and the Phase 5
cutover. Because the candidate URL is operator-supplied, the same command
validates the staging feed route now and the production `djangochat.com` feed
URL at cutover. Covered by
`django_chat/imports/tests/test_live_feed_parity.py`; no test hits the network.

A 2026-06-20 run against the staging feed passed every structural gate (205 = 205
items; matching GUID set/order, latest episode, titles, publication instants,
durations, and enclosure types), with only the approved warnings (moved enclosure
URLs, and 16 source-reported-vs-copied byte-length differences). The 2026-05-13
202-vs-204 gap (missing episodes 203 `Deploy on Day One` and 202
`EuroPython 2026`) is closed; staging has since been re-imported. The enclosure
copied-byte-size gate is validated too: a CDN HEAD sweep (feed `length` vs the
real object) and a read-only on-staging DB check (feed `length` vs recorded
`copied_byte_size`) both passed 205/205. Staging is a verified feed-parity match;
no staging changes are needed.

### Phase 3: Build URL Compatibility Redirects

Before `djangochat.com` points at this repo, implement and test redirects or
route aliases for known public URLs:

- `/` to the show experience
- `/episodes` and `/episodes/` to the episode index
- `/episodes/<slug>` and `/episodes/<slug>/` to the episode detail
- `/episodes/<slug>/transcript` and `/episodes/<slug>/transcript/` to the
  transcript page when a transcript exists
- optional friendly feed alias to the final django-cast feed URL
- do not redirect `/episodes/feed/rss.xml` to the podcast feed unless the
  latest-entries feed is intentionally retired; it is a different feed

Do not invent broad redirects for unknown Simplecast paths. The old Simplecast
site returned HTTP 200 for many arbitrary paths, so status-code probing is not
a safe source of redirect rules.

Status: this phase is largely implemented. `/` already 302-redirects to the
episode index, and the trailing-slash forms (`/episodes`, `/episodes/<slug>`,
`/episodes/<slug>/transcript`) are handled by Django's `APPEND_SLASH` (301 to the
canonical slashed route). The optional friendly feed alias is implemented:
`/feed/rss.xml` permanently redirects to the canonical podcast feed
(`/episodes/feed/podcast/mp3/rss.xml`), while `/episodes/feed/rss.xml` keeps
serving the latest-entries feed directly. This public URL contract is pinned by
regression tests in `django_chat/imports/tests/test_sample_site_routes.py` so a
future routing change cannot silently break a path. Remaining for cutover: verify
these against the real `djangochat.com` origin during the Phase 4 dry run.

### Phase 4: Production Dry Run

Before any directory update:

- deploy the production app under `djangochat.com` (or a production-equivalent
  hostname), with media publishing to S3/CDN
- import the complete current Simplecast catalog
- copy production media to the final media backend
- confirm the app serves the final candidate feed at the canonical route
- set Wagtail `Site`, canonical URLs, media URLs, RSS auto-discovery, and
  subscribe page URLs for `djangochat.com`
- run strict live feed parity against the app-served production feed URL
- validate the feed in Apple Podcasts Connect
- subscribe to the candidate feed manually in test clients
- test web URL redirects and canonical links
- wait through at least one normal feed cache interval; ideally wait through
  one new episode dry run

No listener-visible feed migration happens in this phase.

Production site cutover gate:

- flip `djangochat.com` DNS/origin from Simplecast to the new production
  infrastructure only after the dry run above is green, and before any
  directory points at a `djangochat.com` feed URL

### Phase 5: Communication And Directory Cutover

1. Announce the move before the final Simplecast-hosted episode if possible.
2. Freeze publishing in Simplecast.
3. Import the latest catalog one final time.
4. Publish all referenced media/artwork to S3/CDN.
5. Confirm the production app serves the final feed at the canonical
   `djangochat.com` route.
6. Run strict live feed parity against the app-served production feed URL.
7. Set `itunes:new-feed-url` in the new production feed to the final production
   feed URL and redeploy/refresh so the served feed includes it. This is a
   self-canonical marker for clients that already reach the new feed.
8. Verify the production feed XML directly.
9. Set Simplecast's **RSS Feed Redirect** (show settings → Distribution →
   Advanced Settings) to the final `djangochat.com` feed URL. This is the
   primary migration lever: it 301-redirects clients polling
   `https://feeds.simplecast.com/WpQaX_cs` to the new feed. (`itunes:new-feed-url`
   was already set in the new feed at step 7; it is not set on the old Simplecast
   feed, which returns a 301 rather than XML once this redirect is active.) Set
   the redirect only after step 8 confirms the new feed is correct, and only
   while the Simplecast account is still open — closing the account first deletes
   the feed and the redirect.
10. Verify the redirect: confirm `https://feeds.simplecast.com/WpQaX_cs` returns
    a 301 to the new URL and that a podcast client following it lands on the new
    feed.
11. Update existing directory listings to the final `djangochat.com` feed URL as
    a backup path that does not depend on the Simplecast redirect persisting.
12. Verify Apple, Spotify, Pocket Casts, Overcast, and a generic RSS client.
13. Publish the next episode only after the redirect, directory updates, and feed
    health are confirmed.
14. Keep the Simplecast account open through at least a four-week transition window, then
    retire it only after the redirect is verified to persist.

### Phase 6: Monitor And Stabilize

For the first week:

- check new feed HTTP status and XML parseability
- check item count and latest GUID
- check the served feed's freshness as clients see it (latest GUID/pubDate plus
  any reverse-proxy/CDN cache age)
- check media HEAD/range behavior for recent and old episodes
- watch web/CDN logs for feed and MP3 errors
- watch Apple/Spotify/Pocket Casts listings for latest episode visibility
- confirm `https://feeds.simplecast.com/WpQaX_cs` still returns a 301 to the new
  feed
- periodically check whether the old Simplecast feed is still receiving traffic
  if analytics are available

For at least four weeks:

- keep `itunes:new-feed-url` in the new feed
- confirm the Simplecast 301 redirect still returns a 301 to the new feed
- keep visible migration messaging on `djangochat.com`
- keep Simplecast account access available until retirement is complete

Long term:

- Simplecast is no longer part of publishing, feed hosting, media hosting, or
  analytics
- keep the new feed URL stable indefinitely
- avoid future feed URL moves; if a move is needed, repeat this plan

## Current Work Items

- Confirm host access to the Simplecast dashboard (or a support escalation path
  via support@simplecast.com) so the **RSS Feed Redirect** can be set before
  account retirement. This is now the primary migration lever, not a fallback,
  so missing access blocks the whole cutover.
- Strict live feed parity tooling is implemented: `compare_django_chat_live_feed`
  (`just compare-live-feed --candidate-url <url>`) compares the live Simplecast
  feed to a specified candidate feed URL through the SSRF guard and enforces the
  Phase 2 hard-failure/warning rules. It can point at any candidate URL — the
  staging feed route now, the production `djangochat.com` feed URL at cutover. A
  2026-06-20 run against the staging feed passed every structural gate
  (205 = 205, only approved warnings), and the enclosure byte sizes were
  confirmed 205/205 against both the actual CDN objects and staging's import DB.
  Note: the command is committed but not yet deployed to staging — deploy this
  slice so operators can run `just compare-live-feed` there directly.
- Add production configuration for `itunes:new-feed-url` and test that staging
  cannot accidentally point at production.
- After deploying the upstream podcast metadata adoption, re-run feed parity
  against the generated/candidate production feed and confirm positive
  `itunes:episode` values are present. Keep the preview episode source value
  `0` as an approved generated-feed omission.
- Normalize or explicitly accept duration formatting differences when parsed
  seconds match.
- Trim imported title whitespace or explicitly preserve source whitespace after
  comparison.
- Re-import staging/production candidate catalog to the current live item count —
  done for staging (2026-06-20 parity run confirmed 205 = 205, with episodes 202
  and 203 present); still required for the production environment at cutover.
- Add media object byte-size checks against actual storage metadata for the
  full catalog.
- URL compatibility redirects are implemented and pinned by tests (see Phase 3):
  `APPEND_SLASH` covers trailing-slash forms, `/` redirects to the episode index,
  and `/feed/rss.xml` aliases the canonical podcast feed. Remaining is to verify
  them against the real `djangochat.com` origin during the Phase 4 dry run.
- Write the final cutover runbook with owners, exact URLs, exact commands, the
  media publish steps and feed-serving/caching config, the Simplecast RSS Feed
  Redirect setup and verification, directory dashboards, communication steps,
  Simplecast retirement timing, and rollback steps.

## Sources

The 2026-06-15 revision (Simplecast 301 as the primary lever) is based on:

- [Simplecast: Can I move my RSS feed away from Simplecast?](https://help.simplecast.com/hc/en-us/articles/21953692033437-Can-I-move-my-RSS-feed-away-from-Simplecast)
- [Simplecast: What is a 301 Redirect?](https://help.simplecast.com/hc/en-us/articles/21953514734877-What-is-a-301-Redirect)
- [Simplecast: Will I Lose Any Subscribers If I Change Podcast Hosts?](https://help.simplecast.com/hc/en-us/articles/21953640255901-Will-I-Lose-Any-Subscribers-or-Listeners-If-I-Change-Podcast-Hosts)
- [Simplecast: Will Apple Podcasts Remove My Show if I Delete My Simplecast Account?](https://help.simplecast.com/hc/en-us/articles/21953664049437-Will-Apple-Podcasts-Remove-My-Show-if-I-Delete-My-Simplecast-Account) — the ordering caveat: deleting the account/show before setting the redirect deletes the feed and drops the show from directories.
- [Transistor: How to forward your Simplecast podcast feed — 301 Redirect](https://support.transistor.fm/en/article/how-to-forward-your-simplecast-podcast-feed-301-redirect-1w0p84x/) — exact dashboard path (Distribution → Advanced Settings → RSS Feed Redirect) and the support@simplecast.com escalation.
- [Apple Podcasts for Creators: Change the RSS feed URL](https://podcasters.apple.com/support/837-change-the-rss-feed-url) — 301 + `itunes:new-feed-url` on the old feed, kept ≥4 weeks.
- [Spotify for Creators: Switching away with a 301 redirect](https://support.spotify.com/us/creators/article/switching-away-from-spotify-for-creators-with-a-301-redirect/)
