# Episode Numbering Research

Status: research and backlog note, not an implementation plan.

## Problem

Imported Django Chat episodes carry their Simplecast/RSS episode numbers in
`EpisodeSourceMetadata.episode_number`. Episodes created directly in Wagtail do
not get that metadata row, because the row is import provenance rather than
canonical publishing data. As a result, manually authored episodes can publish
without a visible episode-number badge and without an `itunes:episode` feed
value.

This matters for both the public site and feed parity. The current feed cutover
analysis already records that staging omits `itunes:episode` for common source
items and has an open item to either preserve that tag or explicitly accept its
absence. Future Wagtail-created episodes need the same answer, otherwise the
site will regress immediately after cutover.

## Current Implementation

- `cast.Episode` comes from django-cast and currently has fields for
  `visible_date`, `podcast_audio`, taxonomy, body, keywords, explicit/block, and
  contributors, but no episode number, season number, or episode type field.
- Django Chat stores imported episode numbers on
  `django_chat.imports.models.EpisodeSourceMetadata.episode_number`, a nullable
  positive integer on a one-to-one import metadata row.
- The importer writes `episode_source.episode_number` into that metadata row and
  uses it for import-derived metadata, source-metadata ordering, and fallback
  slugs.
- The episode list and detail templates render badges from
  `page.django_chat_source_metadata.episode_number`. Manually authored pages
  without source metadata render the empty badge placeholder on the list page
  and no number badge on the detail page.
- django-cast's RSS iTunes item elements currently emit author, subtitle,
  summary, duration, keywords, explicit, and block, but not `itunes:episode` or
  `itunes:episodeType`.
- Django Chat already subclasses django-cast's latest-entries feed for local
  repository and description behavior, so a local feed extension is possible.
  The canonical podcast RSS feed still uses django-cast's podcast feed classes.

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

Assessment: best local path if this is needed before upstream django-cast takes
the feature.

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

Assessment: best long-term shape. If production timing allows, prefer upstream.
If timing does not, implement Option B with a documented future migration path.

## Number Assignment Policy

Do not silently consume a number when an editor only creates a draft. Drafts can
be abandoned, copied, or heavily revised, and gaps would become hard to explain.

Recommended local policy:

1. Show a suggested next number in the Wagtail editor, but let editors override
   it.
2. Assign only when an episode is first published and the canonical number is
   blank.
3. Never change an existing number automatically after first publish.
4. Enforce uniqueness at the database level for non-null numbers within the
   podcast/catalog scope.
5. Use a transaction plus a real serialization mechanism around number
   assignment, such as a dedicated counter row, Postgres advisory lock, or
   sequence. Do not rely on an unlocked "max number + 1" query.
6. Treat trailers and bonus episodes as an explicit editorial decision:
   initially they should not auto-consume the full-episode sequence unless the
   hosts choose otherwise.
7. Cover every publish path. If Wagtail publish hooks do not run for bulk
   publish actions, use a lower-level publish signal or explicitly disable/audit
   bulk publishing for episodes so blank numbers cannot slip through.

The historical imported catalog has episode `0` for the preview. Apple episode
metadata describes positive integer episode numbers in common specs, while the
legacy feed has `0`. Preserve the historical source value for imported parity,
but do not auto-assign `0` to new manual episodes. Before feed output is changed,
decide whether the legacy preview emits `<itunes:episode>0</itunes:episode>` for
source parity or suppresses that tag as a special case.

## Feed Implications

Feed parity and future authoring need one source of truth. The candidate feed
logic should:

- Emit `itunes:episode` when canonical publishing metadata has a number.
- Optionally emit `itunes:episodeType`, defaulting to `full` only if the project
  explicitly accepts that default.
- Continue preserving imported historical numbers after backfill.
- Avoid pulling episode numbers directly from `EpisodeSourceMetadata` once the
  canonical model exists, except during the migration window.
- Coordinate this with the live feed parity checker. Current analysis records
  staging as missing `itunes:episode`; adding it should be treated as satisfying
  source parity for imported items, while any intentional omissions or special
  cases, such as the legacy preview `0`, need to be explicit approved
  differences.

This likely touches django-cast's podcast RSS feed path, not only Django Chat's
latest-entries feed subclass.

## Recommended Backlog Slice

Implement episode publishing metadata before production cutover or before the
first post-cutover Wagtail-authored episode, whichever comes first.

Suggested implementation sequence:

1. Decide upstream-vs-local. Prefer upstream django-cast if timing is acceptable;
   otherwise use a local Django Chat canonical metadata model.
2. Audit imported episode numbers for duplicates, nulls, and legacy special
   values before adding canonical uniqueness constraints.
3. Add canonical metadata and a data migration/backfill from
   `EpisodeSourceMetadata`.
4. Add editor-visible fields or a small admin panel so hosts can confirm or
   override the next number.
5. Add publish-time assignment for blank numbers with database uniqueness,
   transaction protection, and coverage for both normal editor publishing and
   bulk publish paths.
6. Update templates to read canonical publishing metadata.
7. Update podcast feed generation to emit `itunes:episode` and, if modeled,
   `itunes:episodeType`.
8. Update feed parity tooling expectations.
9. Document the host workflow in the Wagtail/admin or host-review docs.

Open decisions before implementation:

- Should this be contributed upstream to django-cast first?
- Should Django Chat model `episode_type` and `season_number` now, or only
  `episode_number`?
- Should trailers/bonus episodes share the main number sequence?
- Should slugs for future manual episodes include numbers, or remain title-only?
- Should editors be required to explicitly accept a suggested number before
  publish, or should the system auto-fill when blank?
