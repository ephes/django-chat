# Episode Numbering Research

Status: resolved research and backlog note. The upstream-vs-local decision is
resolved in favor of upstream django-cast. Django Chat now adopts django-cast's
canonical podcast publishing metadata fields and opt-in automatic
first-publish numbering for imported podcasts.

## Problem

Imported Django Chat episodes still carry their Simplecast/RSS episode numbers
in `EpisodeSourceMetadata.episode_number` as source provenance. Canonical
publishing metadata now lives on upstream `cast.Episode` and `cast.Season`, so
episodes created directly in Wagtail can have editor-visible episode number,
episode type, and season fields without creating fake import provenance rows.

This matters for both the public site and feed parity. The generated feed now
has a canonical source for `itunes:episode`, `itunes:episodeType`,
`itunes:season`, `podcast:episode`, and `podcast:season` when those fields are
set. Imported podcasts also enable django-cast's automatic numbering so future
blank full episodes receive the next podcast-scoped number on first publish.

## Current Implementation

- `cast.Episode` comes from django-cast and now has canonical publishing fields
  for `episode_number`, `episode_type`, and `season`.
- `cast.Season` stores reusable positive season numbers scoped to a podcast.
- Django Chat stores imported episode numbers on
  `django_chat.imports.models.EpisodeSourceMetadata.episode_number`, a nullable
  positive integer on a one-to-one import metadata row. That row remains source
  provenance, not editorial metadata.
- The importer keeps writing source metadata, and also copies valid positive
  source episode numbers to `Episode.episode_number`. The historical preview
  episode's source number `0` remains only in `EpisodeSourceMetadata`.
- The importer maps valid RSS `itunes:episodeType` values (`full`, `trailer`,
  `bonus`) to `Episode.episode_type`. Explicit `full` is preserved so generated
  sample feeds keep source parity.
- The importer creates or reuses podcast-scoped `cast.Season` rows from valid
  positive Simplecast season numbers and assigns imported episodes to them.
- The importer enables django-cast automatic episode numbering on the imported
  podcast and seeds `Podcast.next_episode_number` to at least one greater than
  the highest existing canonical episode number under that podcast. Re-imports
  do not lower a counter that has already advanced, and they do not re-enable
  automatic numbering after an operator disables it once the counter has been
  seeded.
- The episode list and detail templates render badges from canonical
  `Episode.episode_number` first, with `EpisodeSourceMetadata.episode_number` as
  a temporary compatibility fallback for import gaps.
- django-cast's podcast feed emits `itunes:episode`, `itunes:episodeType`,
  `itunes:season`, `podcast:episode`, and `podcast:season` from those canonical
  fields without changing RSS GUID behavior.

## External Constraints

Apple's episode metadata guidance says RSS-created episodes must include title
and enclosure tags and recommends additional tags such as episode type, episode
number, and release date:

- <https://podcasters.apple.com/support/825-how-to-create-an-episode>

For Apple Podcasts Connect-created episodes, Apple describes episode type,
season number, and episode number as metadata, and says episode numbers are
optional and encouraged for episodic shows but mandatory for serial shows;
decimals are not supported. Django Chat is an episodic show, so omitting the
tag is probably not a feed rejection risk, but preserving it is better parity
and keeps numbering out of episode titles.

Wagtail's stable 7.4 docs provide admin hooks such as `after_create_page`,
`before_publish_page`, and `after_publish_page`:

- <https://docs.wagtail.org/en/stable/reference/hooks.html>

The docs explicitly warn that attributes changed in `after_create_page` also
need `save_revision()` because edit and index views use revision data. They
also state that publish hooks only run through Wagtail create/edit views, not
bulk actions. Wagtail also exposes publishing signals for model-level side
effects:

- <https://docs.wagtail.org/en/stable/reference/signals.html>

Those hooks and signals are useful for validation or final assignment, but they
are not a complete editor UX by themselves. If an editor should see or override
the number before publishing, the data should be modeled and surfaced in the
Wagtail edit interface. Wagtail panels support model fields in the editor:

- <https://docs.wagtail.org/en/stable/reference/panels.html>

## Options

### Option A: Reuse `EpisodeSourceMetadata`

Add Wagtail/admin behavior that creates an `EpisodeSourceMetadata` row for
manual episodes and assigns `episode_number` there.

Pros:

- Lowest schema change.
- Current templates already read this field.
- Could get badges working with minimal template churn.

Cons:

- Conceptually wrong: source metadata is raw import provenance, not canonical
  editorial metadata.
- Requires inventing fake values for required fields such as `matching_key` and
  `source_title`, or relaxing the model for non-source rows.
- Makes future feed logic depend on import metadata for episodes that were not
  imported.
- Existing import-repair migrations deliberately scope themselves to
  `EpisodeSourceMetadata`; expanding this model to manual pages increases the
  risk that source-only repair code touches editor-authored content.

Assessment: do not choose this except as a short-lived emergency patch.

### Option B: Local Canonical Publishing Metadata

Add a Django Chat-owned one-to-one model, for example
`EpisodePublishingMetadata`, linked to `cast.Episode` with fields such as:

- `episode_number`, nullable positive integer initially.
- `episode_type`, with Apple-compatible values `full`, `trailer`, and `bonus`
  if we choose to model it now.
- `season_number`, nullable positive integer only if the hosts expect seasons.
- timestamps or audit fields if useful.

Backfill it from `EpisodeSourceMetadata.episode_number` for imported episodes.
Then update templates and feed code to read canonical publishing metadata first,
with source metadata as a temporary fallback during migration.

Pros:

- Separates imported source provenance from editorial publishing metadata.
- Lets manually authored episodes have canonical metadata without fake import
  rows.
- Can be implemented locally without waiting for upstream django-cast.
- Provides a clear bridge from imported historical data to future Wagtail
  authoring.
- Keeps source repair/backfill code scoped to imported content.

Cons:

- Wagtail editor integration is less natural than fields directly on
  `cast.Episode`; adding panels to an upstream model from this project requires
  care.
- A plain one-to-one model is outside Wagtail's page revision, preview, and draft
  serialization flow. If editors need to review or override numbers before
  publish, the implementation needs an explicit Wagtail-aware shape, such as
  page fields upstream or a modelcluster/inline-style integration, rather than a
  hidden side table edited only at publish time.
- Feed generation may need local subclassing or an upstream contribution,
  depending on whether the podcast RSS route can be cleanly swapped.
- Backfilling from `EpisodeSourceMetadata.episode_number` must audit existing
  source data before adding uniqueness constraints. The source field is nullable
  and not unique, so duplicate imported numbers or special legacy values can
  make a migration fail if they are copied blindly into constrained canonical
  metadata.
- If django-cast later adds the same fields upstream, this local model will need
  a migration path.

Assessment: not chosen. Upstream django-cast now provides the canonical fields,
so Django Chat should not add a local side table.

### Option C: Upstream django-cast Episode Fields

Add `episode_number`, `season_number`, and `episode_type` directly to
`cast.Episode` upstream, expose them in its Wagtail panels, and update
django-cast podcast feed generation to emit Apple-compatible tags.

Pros:

- The metadata belongs naturally to podcast episode publishing, not only Django
  Chat.
- Wagtail editor UX is straightforward because the fields live on the page
  model and revision flow.
- Feed support can be implemented once in django-cast and reused by Django Chat
  and Python Podcast if wanted.

Cons:

- Requires upstream design agreement and dependency bump timing.
- Django Chat still needs a backfill from source metadata after the dependency
  bump.
- More coordination risk if this becomes part of the production feed cutover
  critical path.

Assessment: chosen. Django Chat pins a django-cast revision containing these
fields, backfills imported metadata through the import path, and leaves source
metadata as provenance.

## Number Assignment Policy

Do not silently consume a number when an editor only creates a draft. Drafts can
be abandoned, copied, or heavily revised, and gaps would become hard to explain.

Implemented upstream policy:

1. The podcast page owns an opt-in `automatic_episode_numbering_enabled` flag
   and a `next_episode_number` counter.
2. Assign only when an episode is first published and the canonical number is
   blank.
3. Never change an existing number automatically after first publish.
4. Serialize assignment by locking the podcast row while choosing and advancing
   the counter.
5. Skip already used numbers within the podcast before assigning.
6. Treat blank episode type as full; blank/full episodes consume the sequence,
   while trailer and bonus episodes do not.
7. Do not assign for draft saves or future scheduled publishes before their
   go-live time.

The historical imported catalog has episode `0` for the preview. Apple episode
metadata describes positive integer episode numbers in common specs, while the
legacy feed has `0`. Django Chat preserves the historical source value in
`EpisodeSourceMetadata` but does not copy it to `Episode.episode_number`, so
generated feeds intentionally omit `itunes:episode` and `podcast:episode` for
that item.

## Feed Implications

Feed parity and future authoring need one source of truth. The candidate feed
logic should:

- Emit `itunes:episode` and `podcast:episode` when canonical publishing metadata
  has a positive number.
- Emit `itunes:episodeType` when the import source explicitly provided a valid
  value. Django Chat preserves explicit `full` from RSS for feed parity instead
  of relying on the blank-is-full convention.
- Emit `itunes:season` and `podcast:season` when imported Simplecast data has a
  valid positive season number.
- Continue preserving imported historical source values after backfill.
- Avoid pulling episode numbers directly from `EpisodeSourceMetadata` except as
  a temporary public badge fallback during migration/import gaps.
- Treat the preview episode's source `0` as an approved generated-feed omission.

## Recommended Backlog Slice

The adoption/backfill and automatic-numbering slice is implemented:

1. django-cast upstream metadata support is used as the canonical model.
2. Imported positive episode numbers, valid episode types, and valid Simplecast
   season numbers are copied onto `cast.Episode`/`cast.Season`.
3. The preview source episode `0` remains provenance only.
4. Public badges read canonical metadata first.
5. Generated podcast feeds emit the upstream iTunes and Podcasting 2.0 tags for
   valid imported metadata.
6. Feed smoke checks assert positive episode-number parity and the approved
   preview omission.
7. Imported podcasts enable django-cast automatic numbering and seed the next
   counter from existing canonical episode numbers under the podcast.

Remaining follow-ups:

- Document and verify the staging/production host workflow after deployment and
  re-import.
- Should slugs for future manual episodes include numbers, or remain title-only?
- Should editors get a preview/suggested number in the Wagtail form before
  publish, or is publish-time assignment enough?
