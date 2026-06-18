# Feed Cutover Analysis

Date: 2026-05-13 (revised 2026-06-15: Simplecast's native 301 RSS Feed Redirect
is now the primary migration lever, reversing the original "Simplecast will not
redirect" decision; see "Key Constraint" and "Sources").

This document is the production feed migration plan for replacing the current
Simplecast-served Django Chat site/feed with output from this repository.
Staging can prove the app works, but feed cutover can affect every subscribed
listener.

## Fixed Decisions

The production migration has these known decisions:

- `djangochat.com` remains the canonical site domain.
- the podcast feed will move from Simplecast to this repo.
- the production podcast feed and audio enclosures will be served from S3/CDN
  under `djangochat.com` or a Django Chat-controlled media hostname.
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

The likely final self-hosted feed URL is an S3/CDN-served object exposed under
`djangochat.com`, for example:

- `https://djangochat.com/episodes/feed/podcast/mp3/rss.xml`

That final URL can still be hidden behind a friendlier same-domain alias such
as `https://djangochat.com/feed/rss.xml`, but the actual canonical feed URL
must be chosen once and then kept stable.

Operationally, django-cast can be the feed generator, but the production
distribution artifact should be a static RSS XML object published to S3/CDN.
That means cutover validation must check both the generated Django/django-cast
feed and the exact CDN-served XML that podcast clients will fetch.
The intended publish path is: django-cast generates the podcast RSS, the
deployment/publish step writes that XML to the chosen S3 object path, and the
CDN serves that object at the canonical `djangochat.com` feed URL.

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

Conclusion: the current staging feed proves the basic shape, but it is not a
production feed cutover candidate yet.

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
- the generated django-cast feed is correct, but the static S3/CDN copy is
  stale, missing the latest episode, or served with the wrong content type

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
- monitor the exact S3/CDN-served feed object, not only the Django origin

### Directory Migration Splits The Audience

Without an old-feed redirect, directories are the main migration lever, and each
directory can behave differently.

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
- CDN invalidation or object upload order exposes a new feed before all
  referenced MP3/artwork objects are available
- the CDN-served feed has the wrong `Content-Type`, compression, cache headers,
  or stale object version
- signed or expiring URLs are accidentally used in RSS
- Podtrac/Simplecast analytics redirects are removed without host approval
- dynamic ad insertion or ad-marker behavior changes

Mitigation:

- compare generated enclosure length to actual stored object byte size
- sample-download and hash representative MP3 files
- test HTTP HEAD and range requests against production media URLs
- keep feed enclosure URLs public, stable, HTTPS, and non-expiring
- publish media objects before publishing feed XML that references them
- verify the exact CDN response headers for feed, artwork, and MP3 URLs
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

The main migration shape: a Simplecast 301 RSS Feed Redirect to an S3/CDN-served
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

### Static Feed Publishing

The feed should be generated from Django/django-cast, then published as a static
object to S3/CDN.

Required behavior:

- upload referenced media/artwork objects before the RSS object
- publish RSS atomically enough that clients do not see half-published state
- use correct `Content-Type`, cache headers, and invalidation behavior
- retain the last known-good feed object for rollback comparison
- make the publish command idempotent and observable

### Communication Window

Because the old feed will not redirect, communication is part of the technical
plan, not a nice-to-have.

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

The chosen canonical URL must be the exact S3/CDN-served URL that directories
and podcast clients fetch. Once directories are updated, do not change it again.

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

The current staging feed would fail this phase because it has 202 items while
Simplecast has 204; it is missing episode 203,
`Deploy on Day One - Calvin Hendryx-Parker`, and episode 202,
`EuroPython 2026 - Mia Bajic`.

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

### Phase 4: Production Dry Run

Before any directory update:

- deploy the production app and S3/CDN feed/media publishing path under
  `djangochat.com` or a production-equivalent hostname
- import the complete current Simplecast catalog
- copy production media to the final media backend
- render the final candidate feed XML and publish it to the final S3/CDN path
- set Wagtail `Site`, canonical URLs, media URLs, RSS auto-discovery, and
  subscribe page URLs for `djangochat.com`
- run strict live feed parity against the exact S3/CDN-served XML
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
5. Generate and publish the final RSS XML to S3/CDN.
6. Run strict live feed parity against the exact CDN-served XML.
7. Set `itunes:new-feed-url` in the new production feed to the final production
   feed URL and republish the RSS object. This is a self-canonical marker for
   clients that already reach the new feed.
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
- check the exact CDN object version/ETag or equivalent freshness marker
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
- Add strict live feed parity tooling that compares the current Simplecast feed
  to a specified candidate feed URL, including the exact S3/CDN-served XML.
- Add a production feed publish step that generates django-cast RSS and writes
  the static XML artifact to S3/CDN with correct headers and invalidation.
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
- Re-import staging/production candidate catalog so it includes episodes 202
  and 203 before any further feed cutover review.
- Add media object byte-size checks against actual storage metadata for the
  full catalog.
- Implement and test `djangochat.com` URL compatibility redirects for known
  Simplecast page paths and django-cast route-shape differences.
- Write the final cutover runbook with owners, exact URLs, exact commands,
  S3/CDN publish steps, the Simplecast RSS Feed Redirect setup and verification,
  directory dashboards, communication steps, Simplecast retirement timing, and
  rollback steps.

## Sources

The 2026-06-15 revision (Simplecast 301 as the primary lever) is based on:

- [Simplecast: Can I move my RSS feed away from Simplecast?](https://help.simplecast.com/hc/en-us/articles/21953692033437-Can-I-move-my-RSS-feed-away-from-Simplecast)
- [Simplecast: What is a 301 Redirect?](https://help.simplecast.com/hc/en-us/articles/21953514734877-What-is-a-301-Redirect)
- [Simplecast: Will I Lose Any Subscribers If I Change Podcast Hosts?](https://help.simplecast.com/hc/en-us/articles/21953640255901-Will-I-Lose-Any-Subscribers-or-Listeners-If-I-Change-Podcast-Hosts)
- [Simplecast: Will Apple Podcasts Remove My Show if I Delete My Simplecast Account?](https://help.simplecast.com/hc/en-us/articles/21953664049437-Will-Apple-Podcasts-Remove-My-Show-if-I-Delete-My-Simplecast-Account) — the ordering caveat: deleting the account/show before setting the redirect deletes the feed and drops the show from directories.
- [Transistor: How to forward your Simplecast podcast feed — 301 Redirect](https://support.transistor.fm/en/article/how-to-forward-your-simplecast-podcast-feed-301-redirect-1w0p84x/) — exact dashboard path (Distribution → Advanced Settings → RSS Feed Redirect) and the support@simplecast.com escalation.
- [Apple Podcasts for Creators: Change the RSS feed URL](https://podcasters.apple.com/support/837-change-the-rss-feed-url) — 301 + `itunes:new-feed-url` on the old feed, kept ≥4 weeks.
- [Spotify for Creators: Switching away with a 301 redirect](https://support.spotify.com/us/creators/article/switching-away-from-spotify-for-creators-with-a-301-redirect/)
