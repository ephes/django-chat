# Show-Note Backfill Repair Plan

Date: 2026-06-01

## Goal

After deploying this code on any machine with a Django Chat database, one
standard operation must leave episode show notes and metadata in the corrected
state:

- `just manage migrate` repairs existing imported episode rows through an
  idempotent data migration.
- Fresh catalog imports write the corrected structure directly.
- An explicit repair command remains available for dry-run audits and safe
  re-runs on already-running environments.

The repair must not depend on hand-editing Wagtail pages, local staging-only
state, or undocumented SQL.

## Observed Failure

The structured show-note implementation converted recognized headed sections
such as `Links`, `Projects`, `Books`, `YouTube`, `Sponsor`, and `Support the
Show`. Historical Django Chat episodes often start their detail notes with a
bare top-level list instead:

```html
<ul>
  <li><a href="https://example.com">Example</a></li>
</ul>
```

Those unheaded lists were intentionally left as paragraph HTML in the first
implementation. The first repair pass converted the links, but it still
introduced a visible `Links` heading that was not present in the source. The
correct rendered shape should match Simplecast: an episode summary section,
then an episode notes section, with source-authored note headings preserved but
no invented `Links` heading for lists that were unheaded in the source.

Representative affected URLs:

- `https://djangochat.staging.django-cast.com/episodes/mongodb-aaron-bassett/`
- `https://djangochat.staging.django-cast.com/episodes/two-scoops-of-django-daniel-feldroy/`

The same pages on `djangochat.com` represent the intended source shape:
`EPISODE SUMMARY` first, then `EPISODE NOTES`. Because the current production
site is a client-rendered Simplecast experience, curl-level checks may only
return the application shell; use a browser or headless browser when verifying
the rendered production DOM. The public Simplecast API also shows the same
source split: `description` is the summary and `long_description` is the
episode notes.

Older episodes also stored Simplecast Markdown directly, for example
`* [link](...)` lists and `#### SHAMELESS PLUGS` headings. Simplecast renders
that Markdown client-side; staging must convert it so the raw Markdown syntax
does not leak to readers.

The follow-up catalog audit found a broader version of the same content-loss
class: source list items and support paragraphs often contain prose around
links. The structured link-list block cannot faithfully preserve arbitrary
text before, between, or after anchors. The repair therefore only structures
link-only lists. Complex source lists are restored as source HTML so headings,
link labels, punctuation, and surrounding prose remain in the authored order.

One later Simplecast-era support boilerplate used only this three-link list:
`LearnDjango.com`, `Button`, and `Django News`. That source shape renders as
bare links without the intended support sentence. The repair keeps the
structured support heading/icon but renders the known boilerplate as a linked
CTA sentence and hides the bare list.

Some source notes also used Markdown-style hash prefixes inside HTML heading
paragraphs, for example `###Support the Show`. The repair normalizes recognized
show-note headings so those Markdown markers do not render as visible heading
text.

There is a related metadata bug: imported `search_description` currently uses
the long detail/show-note HTML instead of the short episode summary, so URL
previews and meta descriptions can become concatenated note-link text.

## Current Audit Counts

The staging RSS feed and local catalog DB were audited on 2026-06-01. These are
point-in-time counts; future staging imports may change the numbers. The repair
criteria are based on content shape, not on the exact count values.

- Live staging feed items checked: 205.
- Items with detail content: 202.
- Detail sections that start with an unheaded HTML list: 158.
- Detail sections with no structured show-note blocks: 76.
- Detail sections with a legacy leading list plus structured sections later:
  108.
- Older raw Markdown-like detail bodies containing `* [link]` or `####`: 26.
- Some pages have no distinct detail body because their source detail is the
  same as the summary. Rows with a distinct stored source detail but a missing
  imported `detail` block are restored from source metadata.
- Support sections that consist only of the known three-link support
  boilerplate: 13.
- Rendered show-note headings with a visible Markdown hash prefix:
  1 (`boost-your-django-dx-adam-johnon`).

The repair criteria now cover both content shapes:

- Leading unheaded HTML lists are treated as the first episode-notes list only
  when every list item is link-only. Lists with source prose around links,
  linkless items, missing `href` values, or other complex content remain
  source HTML.
- Raw Markdown-like bodies are converted with the narrow Simplecast-era subset:
  bullet links become lists and Markdown headings become show-note headings.
- Paragraph-style `Support the Show` sections are preserved as source copy
  with embedded links. They must not be collapsed into link-list items, because
  that either turns the whole sentence into one link or drops the surrounding
  sentence text. On episode detail pages, their source-preserved heading is
  decorated with the same support heart icon as structured support blocks.
- The known three-link support boilerplate renders as one support CTA sentence
  with the support icon, not as a bare list of links.
- Markdown-style hash prefixes on recognized show-note headings are stripped
  before storing or rendering, so `###Support the Show` becomes
  `Support the Show`.

Roughly 40 leading-list episodes include meaningful text outside anchor tags,
so preserving the original source HTML for complex lists is essential to avoid
losing or reordering source content. The staging support-copy follow-up found
62 source support sections with surrounding paragraph text around embedded
links. The final source-vs-body text audit found zero remaining missing detail
phrases after the source-detail restore. A follow-up staging audit found 13
known three-link support boilerplate sections that needed the CTA sentence
restored:

- `boost-your-django-dx-adam-johnson-ep105-replay`
- `contributing-to-django-david-smith-ep97-replay`
- `git-and-django-50-adam-johnson`
- `django-and-ios-filip-nmeek`
- `pycharms-year-of-django-paul-everitt`
- `becoming-a-django-fellow-natalia-bidart`
- `contributing-to-django-sarah-boyce`
- `web-security-mackenzie-jackson`
- `kolo-for-django-lily-foote`
- `understand-django-matt-layman`
- `accessibility-sarah-abderemane`
- `datasette-llms-and-django-simon-willison`
- `from-django-girls-to-the-django-software-foundation-katia-nakamura`

## Implementation Plan

1. Add reusable repair helpers.
   - Put body conversion in import/backfill code, not only in a migration
     function.
   - Use the same body-repair helper from fresh imports, the management
     command, and the data migration.
   - Add a separate metadata-repair helper for `search_description`; do not
     conflate it with the body JSON helper.
   - Keep both helpers idempotent: a second run must produce zero body changes
     and zero metadata changes.

2. Extend the show-note parser.
   - Treat a leading top-level `<ul>` or `<ol>` in `detail` as an implicit
     episode-notes link list only when each item is link-only.
   - Convert it to `show_note_link_list` with `kind="links"` and
     `show_heading=False`, so it renders under the page-level `Episode Notes`
     heading instead of an invented visible `Links` heading.
   - Preserve list order.
   - Preserve the first anchor as the primary link.
   - Preserve additional anchors as `extra_links`.
   - If a list item has meaningful non-anchor text, keep that whole source
     section as paragraph/source HTML. Do not force the prose into
     `description`, because the block can only render descriptions after the
     links and would reorder phrases such as `Subreddits: ... and ...`.
   - Keep unsafe, unsupported, linkless, or malformed lists as paragraph HTML.
   - Convert the narrow legacy Markdown subset used by old Simplecast notes:
     `* [label](url)` or `- [label](url)` bullets and Markdown headings such
     as `#### SHAMELESS PLUGS`.
   - Leave paragraph-style `Support the Show` sections as paragraph HTML so
     the full sentence and embedded links render as authored.
   - Decorate source-preserved `Support the Show` headings with the support
     heart icon at detail-page render time, without changing their stored block
     type or paragraph copy.
   - Render the known three-link `Support the Show` boilerplate as a structured
     support block with the heading/icon, a linked CTA sentence, and no visible
     bare list.
   - Preserve source-authored `Links`, `Projects`, `Books`, `YouTube`,
     `Shameless Plugs`, `Sponsors`, and `Sponsoring Options` headings.
   - When stored source detail metadata exists, use it as the authoritative
     body source for the `detail` block so previously collapsed sections can be
     rebuilt exactly.

3. Restore rendered summary/note headings.
   - Render `Episode Summary` before the `overview` body section on episode
     detail pages.
   - Render `Episode Notes` before the `detail` body section on episode detail
     pages.
   - Keep source-authored show-note headings visible below `Episode Notes`.
   - Do not store these wrapper headings in `Episode.body`, because list cards
     and feeds reuse the body blocks differently.

4. Repair metadata.
   - Change the importer so `page.search_description` comes from
     `_episode_summary()` rather than `_episode_description()`.
   - Backfill existing imported pages to the summary-derived value using
     migration-safe in-database data. The preferred source is the existing
     `overview` body block, stripped of HTML, because it was populated from the
     import summary. If no overview is available, fall back to
     `EpisodeSourceMetadata.simplecast_description`, then
     `EpisodeSourceMetadata.rss_description_html`, stripped of HTML.
   - Do not call `_episode_summary()` from the data migration; it expects live
     `EpisodeSourceData`, not historical ORM rows.
   - Leave raw source metadata fields unchanged.

5. Add an explicit repair command.
   - Proposed command:
     `just manage repair_django_chat_show_notes --dry-run`
   - Proposed write mode:
     `just manage repair_django_chat_show_notes --write`
   - The command should report:
     - total episodes scanned;
     - body rows that would change;
     - metadata rows that would change;
     - source-derived detail blocks restored;
     - converted leading lists;
     - generated implicit `Links` headings hidden;
     - leading lists skipped because source prose must stay as source HTML;
     - support-copy sections restored from source detail;
     - raw Markdown-like bodies converted or still reportable;
     - per-episode slug, title, and action when verbose.
   - These are action counters for rows that need repair. Intentionally
     preserved complex source lists should not keep reporting as skipped after
     the stored body matches the desired source-derived detail block.
   - Every converted implicit leading list also hides its generated `Links`
     heading, so `implicit_link_list_headings_hidden` is expected to match
     `implicit_link_lists_converted` for newly converted rows.

6. Add data migrations.
   - Do not edit `imports.0004`; it has already run on staging.
   - `imports.0005_repair_episode_show_notes` calls the body-repair helper and
     the metadata-repair helper in write mode.
   - `imports.0006_repair_remaining_implicit_show_note_lists` covers the
     discovered linkless-list-item fallback after `0005` had already run on
     staging.
   - `imports.0007_hide_implicit_link_list_headings` hides the generated
     `Links` heading for already-migrated implicit source lists.
   - `imports.0008_convert_legacy_markdown_show_notes` converts the old
     Simplecast Markdown-like bodies.
   - `imports.0009_restore_support_show_copy` restores paragraph-style
     `Support the Show` copy from source metadata for already-migrated rows.
   - `imports.0010_restore_source_detail_show_notes` restores the full
     source-derived `detail` block for rows where structured conversion had
     dropped or reordered source prose.
   - `imports.0011_restore_support_boilerplate_copy` restores the CTA sentence
     for the known three-link support boilerplate while keeping the support
     icon.
   - `imports.0012_strip_markdown_hashes_from_show_note_headings` strips
     Markdown-style `#` prefixes from recognized show-note headings that were
     already stored in imported bodies.
   - Reverse migrations should be no-ops because reconstructing the exact old
     StreamField serialization is not required and would be risky.

7. Update fresh imports.
   - `_episode_body()` should continue using the parser so new imports do not
     regress.
   - The importer should write summary-based `search_description` from the
     start.

8. Verify locally and on staging.
   - Run the repair command in dry-run mode before migrations write data.
   - Run `just test`.
   - Run the configured hook runner (`prek` in this repo).
   - Deploy to staging and run `just manage migrate`.
   - Run the repair command again in dry-run mode; expected second-run body
     change count is zero.

## Test Plan

Add focused tests for:

- A leading unheaded link-only HTML list converts to
  `show_note_link_list(kind="links")`.
- A leading or headed HTML list with prose around links remains source HTML.
- `mongodb-aaron-bassett`-style content converts the leading list while keeping
  later `Support the Show` structured.
- `two-scoops-of-django-daniel-feldroy`-style content converts the leading list
  even when there are no later recognized sections.
- List item text outside anchors is not dropped or turned into an oversized
  link.
- Multi-link list items preserve primary and extra links.
- Invalid links, linkless items, or unsupported nested structures stay as
  paragraph/source HTML.
- Running the repair twice is idempotent.
- Existing already-structured simple sections remain unchanged.
- `search_description` uses the short summary, not long show notes.
- Episode detail pages render `Episode Summary` and `Episode Notes`.
- Unheaded source lists do not render an invented visible `Links` heading.
- Raw Markdown-like notes become rendered links/headings instead of literal
  Markdown syntax.
- Paragraph-style `Support the Show` sections render as full copy with only
  the embedded source links clickable.
- Three-link `Support the Show` boilerplate sections render the support icon
  and CTA sentence instead of a bare list.
- Feed-safe rendering still emits static `h3`, `p`, `ul`, `li`, and `a`
  markup without icon chrome.

## Staging Verification URLs

Verify these manually after migration:

- `https://djangochat.staging.django-cast.com/episodes/mongodb-aaron-bassett/`
- `https://djangochat.staging.django-cast.com/episodes/two-scoops-of-django-daniel-feldroy/`
- `https://djangochat.staging.django-cast.com/episodes/django-tasks-jake-howard/`
- `https://djangochat.staging.django-cast.com/episodes/breaking-django/`
- `https://djangochat.staging.django-cast.com/episodes/teaching-python-michael-kennedy/`
- `https://djangochat.staging.django-cast.com/episodes/django-vs-flask-michael-herman/`
- `https://djangochat.staging.django-cast.com/episodes/from-beginner-to-software-engineering-manager-raymond-traylor/`
- `https://djangochat.staging.django-cast.com/episodes/boost-your-django-dx-adam-johnon/`
- `https://djangochat.staging.django-cast.com/episodes/boost-your-django-dx-adam-johnson-ep105-replay/`
- `https://djangochat.staging.django-cast.com/episodes/what-is-django/`
- `https://djangochat.staging.django-cast.com/episodes/translations-andrew-knight/`
- `https://djangochat.staging.django-cast.com/episodes/accessibility-sarah-abderemane/`
- `https://djangochat.staging.django-cast.com/episodes/feed/rss.xml`

Expected results:

- The two affected detail pages render the old first note list under a visible
  `Episode Notes` heading without an invented visible `Links` heading.
- The overview text renders under `Episode Summary`.
- Later structured sections still render in their original order.
- Simple already-structured sample sections are unchanged; complex source lists
  render as the original list HTML.
- Linkless list-item text, malformed source links, and prose around anchors are
  preserved in the original list position.
- The raw Markdown-like sample page renders as HTML links/headings instead of
  literal Markdown syntax.
- The support-copy samples, including `mongodb-aaron-bassett` and
  `from-beginner-to-software-engineering-manager-raymond-traylor`, preserve the
  complete source sentence around the embedded links and show the support heart
  icon on the heading.
- `boost-your-django-dx-adam-johnon` renders `Support the Show`, not
  `###Support the Show`.
- The three-link support boilerplate sample,
  `boost-your-django-dx-adam-johnson-ep105-replay`, renders the support icon
  plus the sentence `This podcast does not have any ads or sponsors...`, not
  only `LearnDjango.com Button Django News newsletter`.
- Feed output remains feed-safe and does not include decorative icon markup.
- Page meta descriptions use the episode summary.

## Rollback And Safety

Before running the migration on staging or production-like data:

- Take a database backup.
- Run the repair command in dry-run mode and save the report.
- Confirm the changed-row count is plausible against the audit counts above.

If a rollback is needed, restore the database backup. The data migration reverse
operation should be a no-op; it should not attempt to synthesize the previous
legacy body JSON.

## Remaining Work After This Repair

This repair covers the staging-visible content regressions found in the
2026-06-01 audit: unheaded HTML note lists, old Simplecast Markdown-like notes,
support paragraphs with embedded links, complex list items with surrounding
text, distinct source detail bodies that were missing after the first
structured-block migration, and the later three-link support boilerplate. After
deployment, keep using the dry-run repair command as the repeatable audit: it
should report zero body changes, zero metadata changes, zero source-detail
restores, zero skipped implicit lists, and zero raw Markdown-like episode
bodies. The follow-up `0012` heading-normalization migration also covers
Markdown-style hash prefixes that were embedded in HTML heading text.
