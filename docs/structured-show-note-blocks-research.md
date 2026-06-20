# Structured Show-Note Blocks Research

Date: 2026-05-30 (icon model added 2026-06-02)

## Recommendation

Use `CAST_POST_BODY_BLOCKS` to add Django Chat-specific show-note blocks only to
the `detail` section of `Post.body`.

The stable block names are:

- `show_note_sponsor`
- `show_note_link_list`
- `show_note_heading` (added with the icon feature, for section headings whose
  body is not a convertible link list / sponsor)

`show_note_link_list` should be generic enough to cover `Links`, `Projects`,
`Books`, `YouTube`, `Groups`, `Shameless Plugs`, `Support the Show`,
`Sponsors`, and `Sponsoring Options`. The implementation should not add
first-class blocks for those categories in the first pass; their differences
are heading text, icon choice, and editor labeling, not separate saved
StreamField schema.

The implementation bumped `django-cast` from `d6ce2c7980baaece847d8495d22832208cd73f88`
to `f795ed5f` (where `CAST_POST_BODY_BLOCKS` was added) and then further to the
current pin `151a4fa8d306def60783d50d7f4f3e052a057533` in `pyproject.toml`.

## Show-Note Icons (auto/override, materialized at save time)

Every show-note section heading carries a decorative circular icon. The model:

- Each block (`show_note_link_list`, `show_note_sponsor`, `show_note_heading`)
  has a `kind` field (editor *intent*, default `"auto"`, choices from the
  `ICON_REGISTRY` in `django_chat/show_notes/icons.py`, edited via the visual
  `IconChoiceWidget`) and a hidden `icon` field (the materialized concrete kind).
- `kind="auto"` derives the icon from the heading via `resolve_icon_kind()`
  (`django_chat/imports/show_notes.py`): exact label match (Links, Support the
  Show, Sponsor, …) → that kind; else a whole-word `sale`/`rabatt`/`offer` or a
  literal `%` → `sale`; else a `dashboard` substring → `dashboards`; else
  `default`. An explicit `kind` is used verbatim.
- The `icon` is **materialized at save time**, not resolved on every render:
  `StructBlock.clean()` (admin Save and Preview), the importer/structuring
  pipeline, and the data migration all set `icon` via `materialize_icon()`.
  Rendering reads `icon`; `display_icon()` falls back to deriving from the
  heading when `icon` is absent (old revisions / un-migrated JSON).
- "Has the editor customized it?" is simply `kind != "auto"`.
- Icons are code-side SVG snippets under
  `templates/cast/django_chat/show_notes/icons/<snippet>.svg`, rendered by the
  `{% show_note_icon kind %}` tag (registry lookup + `default.svg` fallback).
  The picker has an optional admin-only JS live-preview that shows the
  auto-resolved icon as the editor types the heading; it degrades gracefully.

**D5 — every heading gets an icon.** During structuring, every real `<h3>`–`<h6>`
heading is offloaded into a block: a convertible link/sponsor section becomes
`show_note_link_list`/`show_note_sponsor`; any other heading (including
non-convertible known-label sections) becomes a `show_note_heading` with its
body preserved verbatim as a following `paragraph`. A recognised section label
canonicalises the offloaded heading text (e.g. a non-convertible `📚 Books` or
`SHAMELESS PLUGS` list — one with prose around the links — yields heading `Books`
/ `Shameless Plugs`, the icon replacing the source emoji), so it matches its
converted counterparts; unknown headings keep their verbatim text but still
resolve an icon. Empty headings are left as raw content. Episodes structured
before D5 kept such sections as raw `<h3>…</h3>` HTML with no icon; migration
`0017_offload_raw_show_note_headings` re-runs the in-place structuring over
imported bodies to offload them, leaving already-structured blocks (and their
icon overrides) untouched.

D5 also covers **headingless** sources. A leading source list with no heading is
converted to a `show_note_link_list` (iconed `Links`) when its items are cleanly
itemizable. When it is not (items mix prose with links, multiple anchors per
item, …) the list cannot be losslessly itemized, so instead a synthesized iconed
`Links` `show_note_heading` is emitted and the list is preserved verbatim as a
following `paragraph` — the headingless analog of the offload above. This only
applies when the list carries at least one real link; a link-less bullet list is
not a `Links` section and stays unstructured. Re-structuring is idempotent: a
list that already follows its own stored heading block does not regain a
synthesized `Links` heading. Episodes imported before this rule kept such lists
as a bare `<ul>` with no heading/icon; migration
`0019_add_implicit_link_list_headings` re-runs the in-place structuring over
imported bodies to add the heading, leaving already-structured blocks untouched.

The migration `0015_materialize_show_note_icons` brings existing
data forward (icon-only, no HTML re-parse): it materializes `icon` on stored
blocks and normalises system-derived `kind` back to `"auto"`, preserving genuine
overrides. A stored `kind` counts as system-derived (→ `"auto"`) when it is empty,
the deprecated `other`, matches the heading's auto-resolution, **or** is the legacy
`ShowNoteLinkListBlock` default `"links"` on a link-list block — the importer only
ever paired `kind="links"` with the heading `Links`, so `"links"` on a differently
headed link list (e.g. `Books` left at the default) is the old default leaking
through, not an override. That last rule is scoped to link lists: a `"links"` kind
on a heading/sponsor block has no legacy default and stays an override. The
follow-up migration `0016_heal_show_note_icons` re-runs this corrected backfill so
environments that applied the initially-shipped 0015 (which froze those legacy
defaults as `links` overrides) are healed; it is forward-only and idempotent.

## Research Basis

I inspected the local full-catalog import in `db.sqlite3` using read-only Django
ORM queries:

- 201 `EpisodeSourceMetadata` rows and 201 `cast.Episode` rows.
- 196 rows have `simplecast_long_description_html`.
- 200 rows have `rss_content_html`.
- 198 saved episode bodies have a `detail` block.
- 123 saved episode bodies have at least one normalized show-note heading.
- 75 saved episode bodies have detail content but no heading.
- 3 episodes have no detail block: `preview`, `summer-break`,
  `greening-django-chris-adams`.

I parsed every saved `detail` paragraph with BeautifulSoup and compared it with
the stored source metadata fields. I also spot-checked public staging HTML for:

- `django-tasks-jake-howard`
- `django-community-survey`
- `how-to-learn-django`

Those staging pages matched the local heading structure.

## Current Import And Rendering Flow

`django_chat/imports/import_catalog.py` fetches RSS, Simplecast podcast data,
Simplecast episode pages, and Simplecast per-episode details. It merges those
source records into `EpisodeSourceData`.

`django_chat/imports/import_sample.py` builds `Episode.body` like this:

- `overview`: `simplecast.description`, falling back to `rss.description_html`.
- `detail`: `simplecast.long_description_html`, falling back to
  `rss.content_html`, then the overview.
- The detail HTML is passed through `normalize_show_notes_html()`.

`django_chat/imports/show_notes.py` currently normalizes only heading markup:

- It converts all `h4` headings to `h3`.
- It converts plain paragraph labels to `h3` when the label is recognized and
  the next meaningful tag shape is safe.
- List labels: `Books`, `Links`, `Projects`, `Shameless Plugs`, `YouTube`,
  `Groups`.
- Copy labels: `Sponsor`, `Support the Show`.
- It only backfills saved `detail` paragraph blocks, not `overview`.

`django_chat/templates/cast/django_chat/episode.html` renders every body section
inside the public detail-page show notes. `post_body.html` renders `overview`
by default and includes `detail` only when `render_detail` is true. django-cast
feeds call `get_description(..., render_detail=True)`, so detail-only blocks
will still appear in podcast feed item descriptions.

## django-cast API Constraints

The new django-cast API builds each `ContentBlock(section=...)` from built-in
blocks plus `configured_content_blocks(section)`.

`CAST_POST_BODY_BLOCKS` must be a dict keyed by `overview` and/or `detail`. Each
value must be a list or tuple of dotted factory paths. Each factory must return
`(name, block)` where `name` is a non-empty string and `block` is a Wagtail
`Block` instance.

Custom block names cannot collide with built-ins:

- `heading`
- `paragraph`
- `code`
- `image`
- `gallery`
- `embed`
- `video`
- `audio`

Invalid settings are reported through django-cast system checks, and runtime
block construction falls back to built-ins so Django can start and display the
check errors.

Saved StreamField JSON stores block names. After these blocks are used in saved
content, renaming or removing block names can make existing content fail to load
or render. Prefix the block names with `show_note_` and treat them as permanent
schema.

## Catalog Findings

All normalized show-note headings in saved detail bodies are currently `h3`.
There are 176 total headings.

| Heading key | Sections | Episodes | Shape | Representative slugs |
| --- | ---: | ---: | --- | --- |
| `Support the Show` | 74 | 74 | 61 paragraph, 13 list | `django-community-survey`, `boost-your-django-dx-adam-johnon`, `django-unicorn-adam-hill` |
| `Sponsor` | 34 | 34 | 20 paragraph, 8 list, 6 two-paragraph | `michael-kennedy`, `improving-django-adam-hill`, `django-tasks-jake-howard` |
| `Links` | 14 | 14 | all lists | `djangocon-us-2025-recap`, `django-survey-2025-jeff-triplett`, `django-tasks-jake-howard` |
| `YouTube` | 14 | 14 | all one-item lists | `djangocon-us-2025-recap`, `building-a-django-api-framework-faster-than-fastapi`, `boost-your-github-dx-adam-johnson` |
| `Shameless Plugs` | 12 | 12 | all lists | `what-is-django`, `lacey-williams-henschel`, `django-rest-framework-replay` |
| `Projects` | 10 | 10 | all lists | `djangocon-us-2025-recap`, `django-fellow-jacob-walls`, `django-tasks-jake-howard` |
| `Books` | 10 | 10 | all lists | `djangocon-us-2025-recap`, `django-on-the-med-paolo-melchiorre`, `django-tasks-jake-howard` |
| `Groups` | 3 | 3 | all lists | `how-to-learn-django`, `how-to-learn-django-ep2-replay`, `how-to-learn-django-replay` |
| `Sponsors` | 2 | 2 | all lists | `django-for-the-meat-industry-bryton-wishart`, `pretix-raphael-michel` |
| `Sponsoring Options` | 2 | 2 | all lists | `django-rest-framework-ep5-replay`, `django-rest-framework-replay` |
| `Black Friday Sale` | 1 | 1 | paragraph | `optimizing-django-queries-jamie-matthews` |

Common heading orders:

- 72 episodes: `Support the Show` only.
- 20 episodes: `Sponsor` only.
- 10 episodes: `Links`, `Projects`, `Books`, `YouTube`, `Sponsor`.
- 4 episodes: `Links`, `YouTube`, `Sponsor`.
- 9 episodes: `Shameless Plugs` only.
- 2 episodes: `Groups`, `Shameless Plugs`.
- The remaining 6 headed episodes use less-common combinations.

Emoji-prefixed headings are a recent convention:

| Prefix | Count | Heading |
| --- | ---: | --- |
| `🔗` | 14 | `Links` |
| `🎥` | 14 | `YouTube` |
| `📦` | 10 | `Projects` |
| `📚` | 10 | `Books` |
| `🤝` | 1 | `Sponsor` |

There is also one malformed raw heading, `###Support the Show`, which the
current label normalizer still classifies as `Support the Show` after stripping
leading punctuation.

Target headed sections contain 480 links. All but one have `http` or `https`
URLs. The only invalid target-section href is `revsys.com` in
`django-survey-2025-jeff-triplett`; a backfill can canonicalize it to
`https://revsys.com`.

Recent structured sections are list-heavy:

- `Projects`: 28 items, all one-link items.
- `Books`: 31 list items and 32 links. Sixteen item labels contain ` by `,
  but the catalog also uses dash-separated author text and media items, so
  author extraction should be conservative.
- `Links`: 91 list items and 105 links. Most items have one link, but some
  have two or three links in one list item.
- `YouTube`: 14 items, all one link to the Django Chat YouTube channel.

Older detail bodies are less structured. The 75 no-heading episodes include
raw Markdown-like bullets or plain HTML lists. The first block implementation
should leave those paragraphs alone unless a broader historical show-note
cleanup is explicitly scoped.

## Block Schemas

Register these factories only under `CAST_POST_BODY_BLOCKS["detail"]`.

```python
CAST_POST_BODY_BLOCKS = {
    "detail": [
        "django_chat.show_notes.blocks.sponsor_block",
        "django_chat.show_notes.blocks.link_list_block",
        "django_chat.show_notes.blocks.heading_block",
    ],
}
```

All three blocks additionally carry the `kind` (intent) + hidden `icon`
(materialized) fields described in [Show-Note Icons](#show-note-icons-autooverride-materialized-at-save-time).

### `show_note_sponsor`

Wagtail icon: `tag`

Public/detail icon: the `sponsors.svg` snippet (a person-in-circle / avatar
mark), selected via the materialized `icon` (the default "Sponsor" heading
auto-resolves to `kind="sponsor"`).

Schema:

- `heading`: `CharBlock`, default `Sponsor`.
- `kind`: `ChoiceBlock`, default `auto` (icon picker).
- `icon`: hidden `CharBlock` (materialized concrete kind).
- `sponsor_name`: `CharBlock`, required.
- `sponsor_url`: `URLBlock`, required.
- `copy`: `RichTextBlock`, optional, limited to links, bold, italic.
- `coupon_code`: `CharBlock`, optional.

Backfill behavior:

- Convert `Sponsor` and `🤝 Sponsor` when the section has at least one link.
- The first link becomes `sponsor_name` and `sponsor_url`.
- Preserve paragraph sponsor copy in `copy`.
- List-only sponsors such as Mailtrap and TalkPython become sponsor blocks
  with blank `copy`.
  - First-slice implementation note: only single-link list sponsors convert;
    multi-link or mixed paragraph/list sponsor sections stay as paragraph HTML
    so the importer does not silently drop sponsor links.
- Leave plural `Sponsors` and `Sponsoring Options` as `show_note_link_list`,
  not `show_note_sponsor`, because those sections are lists of options rather
  than a single episode sponsor placement.

### `show_note_link_list`

Wagtail icon: `link`

Public/detail icon: determined by the materialized `icon` field, which maps to an
SVG snippet via `ICON_REGISTRY` (see
[Show-Note Icons](#show-note-icons-autooverride-materialized-at-save-time));
unknown kinds fall back to `default.svg`.

Schema:

- `heading`: `CharBlock`, default `Links`.
- `kind`: `ChoiceBlock`, default `auto` (icon picker).
- `icon`: hidden `CharBlock` (materialized concrete kind).
- `show_heading` / `show_items`: `BooleanBlock`, default `True`.
- `intro`: `RichTextBlock`, optional, limited to links, bold, italic.
- `items`: `ListBlock` of link items, minimum one item.

This one schema is the concrete schema for links, projects, books, and the
other list-like show-note categories; the materialized `icon` (derived from
`kind`/heading) controls the icon and CSS hook.

Link item schema:

- `title`: `CharBlock`, required.
- `url`: `URLBlock`, required.
- `description`: `RichTextBlock`, optional, limited to links, bold, italic.
- `extra_links`: optional `ListBlock` of `{title, url}` pairs.

Backfill behavior (all conversions store `kind="auto"` with the `icon`
materialized to the named kind, e.g. `Links` → icon `links`; the labels below
name the resulting icon, not a stored `kind`):

- Convert `Links` (icon `links`).
- Convert `Projects` (icon `projects`). The catalog currently has 28 project
  items, all one-link items, so this is the safest list conversion.
- Convert `Books` (icon `books`). Use the first anchor text as `title` and the
  first href as `url`.
- Convert `YouTube` (icon `youtube`); do not create a dedicated YouTube block.
- Convert `Groups` (icon `groups`); only 3 episodes use it.
- Convert `Shameless Plugs` (icon `shameless_plugs`); only 12 older episodes
  use it and its content is ordinary links.
- Convert `Support the Show` (icon `support`) when the section is structurally
  safe. Keep paragraph copy in `intro` and extract linked calls to action into
  `items`. This is not a sponsor block because the copy repeatedly says the
  show had no sponsor.
  - First-slice implementation note: paragraph-only support sections use the
    full paragraph text as the link item title and leave `intro` blank, so the
    same support link is not rendered twice. Support sections that already have
    list items can still render intro copy before the list.
- Convert `Sponsors` (icon `sponsors`) and `Sponsoring Options` (icon
  `sponsoring_options`); both store `kind="auto"`.
- For list items with multiple anchors, use the first anchor as the primary
  item and store remaining anchors in `extra_links`. Preserve surrounding item
  text in `description` when needed.
  - First-slice implementation note: `description` is not populated yet; richer
    surrounding-text preservation is deferred to the full-catalog backfill
    command/reporting slice.
- Do not add an `authors` field in the first-pass schema. Preserve the full
  book label in `title`; the real data mixes `Title by Author`,
  `Title - Author`, publications, films, and periodicals, so automatic author
  splitting is easy to get wrong. If editors later need curated author metadata,
  add an optional field to `show_note_link_list` with a deliberate migration.

## Section Placement

Register both blocks for `detail` only.

Reasons:

- Imported show-note headings occur in the episode detail content, not the
  overview summary.
- Current `normalize_episode_body_show_notes()` intentionally touches only
  `detail`.
- The public detail page already shows every body section below "Show notes".
- Feeds render detail content with `render_detail=True`, so detail-only blocks
  still reach podcast feed descriptions.
- Adding these blocks to `overview` would expose editor choices that do not
  match the existing catalog and could leak long show-note lists into episode
  index cards.

## Rendering Expectations

For public detail pages:

- Render a semantic section with a visible `h3`.
- Preserve canonical heading text: `Links`, `Projects`, `Books`, `YouTube`,
  `Sponsor`, and so on.
- Use `ul`/`li` for list blocks.
- Keep sponsor copy as ordinary paragraph HTML with one clear sponsor link.
- Style icons as decoration only; the heading text remains the accessible
  label.
- Keep output usable when CSS or JavaScript is absent.

Implementation note: the first UI slice keeps structured blocks close to the
old plain show-note HTML while adding decorative dark-green circular heading
icons sized to match contributor avatars. List link text aligns with the
heading text column, and dark-green custom bullets sit centered under the icon
column. Structured headings strip source emoji/punctuation prefixes such as
`🔗`, `📦`, `📚`, `🎥`, and `🤝` because the decorative icon now carries that
visual role; paragraph fallbacks still preserve source HTML unchanged.

For feeds and API HTML when `render_for_feed` is true:

- Render static HTML only: `h3`, `p`, `ul`, `li`, and `a`.
- Do not render SVG icon chrome, buttons, collapsible UI, script hooks, or
  iframe/embed behavior.
- Do not rely on CSS for meaning.
- Avoid `target="_blank"` in feed output.
- Use absolute URLs where a URL is internal or relative. Existing show-note
  target URLs are external, but the template should not assume that forever.

For Wagtail API HTML:

- The django-cast `HtmlField` defaults to feed-safe rendering unless the request
  passes `render_for_feed=0`, `false`, or `no`.
- Custom block templates must render correctly in both modes.
- API HTML should include the same ordered show-note content as the public
  detail page, with feed-safe markup by default.

## Wagtail Editor UX

- Label the blocks as `Show-note sponsor` and `Show-note link list` so editors
  do not confuse them with generic content blocks.
- Keep `heading` editable but defaulted.
- Use `kind` on `show_note_link_list` instead of adding many rarely-used blocks
  to the StreamField chooser.
- Use item labels from `title` so collapsed list items are readable.
- Keep rich text features narrow. These sections are structured links, not
  article prose.
- Put these blocks after the built-ins through `CAST_POST_BODY_BLOCKS["detail"]`;
  django-cast appends custom blocks after built-ins.
- Document that block names are stable and must not be renamed after editors or
  backfills save content.

## Parser And Backfill Plan

Add a parser that transforms only safe, normalized detail paragraph HTML into
structured detail child blocks.

The parser should:

1. Read `Episode.body` as StreamField JSON.
2. Process only `detail` blocks and only `paragraph` children.
3. Parse the paragraph HTML with BeautifulSoup.
4. Walk top-level nodes in order.
5. Split matching heading sections at `h1` through `h6`, though current saved
   data uses `h3`.
6. Normalize labels with the existing rules: collapse whitespace, strip a
   trailing colon, casefold, and strip leading non-alphanumeric characters.
7. Convert only recognized labels and safe shapes.
8. Preserve all unrecognized, malformed, or unsafe content as paragraph HTML.
9. Preserve original order by replacing one paragraph with a sequence of
   paragraph and structured blocks.
10. Be idempotent when run on already-structured detail content.

Conversion map (every block stores `kind="auto"`; the listed icon is what the
heading auto-resolves to and is materialized into `icon`):

| Normalized label | Target block | Icon |
| --- | --- | --- |
| `links` | `show_note_link_list` | `links` |
| `projects` | `show_note_link_list` | `projects` |
| `books` | `show_note_link_list` | `books` |
| `youtube` | `show_note_link_list` | `youtube` |
| `groups` | `show_note_link_list` | `groups` |
| `shameless plugs` | `show_note_link_list` | `shameless_plugs` |
| `support the show` | `show_note_link_list` | `support` |
| `sponsors` | `show_note_link_list` | `sponsors` |
| `sponsoring options` | `show_note_link_list` | `sponsoring_options` |
| `sponsor` | `show_note_sponsor` | `sponsor` |
| any other heading | `show_note_heading` (D5) | `resolve_icon_kind` (`sale`/`dashboards`/`default`) |

Backfill criteria:

- Convert list sections only when every item is link-only and has at least one
  usable link. If item text appears before, between, or after links, keep the
  section as source HTML so the authored prose order is preserved.
- Convert sponsor sections only when a first link can be extracted.
- Canonicalize missing URL schemes only when safe, for example `revsys.com` to
  `https://revsys.com`.
- If any section has unexpected nested structure, invalid URLs, no links, or
  prose around links, keep that section as paragraph/source HTML.
- The first implementation left the 75 no-heading detail bodies unchanged.
  Follow-up repair planning for the unheaded leading-list and raw Markdown-like
  cases lives in [`show-note-backfill-repair.md`](show-note-backfill-repair.md);
  that repair is implemented through new idempotent data migrations and a
  command rather than by editing the already-applied first migration.
- `Black Friday Sale` (and other non-list headings) are offloaded by D5 into a
  `show_note_heading` whose `icon` auto-resolves to `sale` (via the `%`/`sale`
  rule in `resolve_icon_kind`); the section body is preserved verbatim.
- Provide a dry-run command that reports planned conversions and source-detail
  restores by episode slug before writing anything.

The importer should use the same parser for future catalog imports so new
episodes do not regress to paragraph-only structured show notes. Existing source
metadata fields should remain unchanged.

## Tests For The Implementation Slice

Add unit tests for block factories and settings:

- `CAST_POST_BODY_BLOCKS["detail"]` loads all three factories
  (`show_note_sponsor`, `show_note_link_list`, `show_note_heading`).
- No block name collides with built-in django-cast names.
- Blocks are not registered for `overview`.
- The django-cast system check passes with the configured factory paths.

Add parser tests:

- Emoji headings convert correctly: `🔗 Links`, `📦 Projects`, `📚 Books`,
  `🎥 YouTube`, `🤝 Sponsor`.
- Legacy headings convert correctly: `SHAMELESS PLUGS`, `Groups`,
  `Support the Show`, `###Support the Show`.
- Sponsor paragraph copy converts to `show_note_sponsor`.
- List-only sponsor converts to `show_note_sponsor`.
- `Projects` and `Books` convert to `show_note_link_list` with `kind="auto"`
  and the matching materialized `icon`.
- Plural `Sponsors` and `Sponsoring Options` convert to
  `show_note_link_list`.
- `Support the Show` list variants convert to `show_note_link_list`
  (`kind="auto"`, icon `support`); paragraph-only variants offload the heading
  to `show_note_heading` (icon `support`) with the copy as a following paragraph.
- Multi-link list items preserve primary and extra links.
- `Books` does not automatically split authors; the original label stays in
  `title`.
- Invalid or unsupported sections are preserved as paragraph HTML.
- Running the parser twice produces no further change.

Add import/backfill tests:

- `_episode_body()` can emit structured detail blocks from a Simplecast long
  description while leaving overview unchanged.
- A dry-run backfill reports counts without saving.
- A write-mode backfill updates only intended episodes and fields.
- Existing paragraph-only episodes without headings are unchanged.

Add rendering tests:

- Public detail pages render the structured show notes in order.
- Feed descriptions include detail show-note blocks with feed-safe markup.
- Feed output does not include interactive/icon-only markup.
- Wagtail API HTML renders these blocks with default feed-safe output.
- API HTML with `render_for_feed=0` renders the public-detail variant.

## Risks

- Saved StreamField content depends on block names. Rename or remove
  `show_note_*` blocks only with a deliberate data migration.
- A dependency bump is required before Django Chat can consume
  `CAST_POST_BODY_BLOCKS`.
- Support copy is common but historically not the same as sponsor copy. Mapping
  it into `show_note_sponsor` would misrepresent many older episodes.
- Recent episodes have clean sections, but older no-heading episodes are not a
  safe target for automatic structuring yet.
- Author extraction from book items is not reliable enough for an automatic
  first-pass backfill.
- The parser must preserve paragraph HTML around structured sections or it can
  silently drop imported source content.
