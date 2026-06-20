# Comments activation

Date: 2026-06-20

## Background

The Django Chat staging site
(`https://djangochat.staging.django-cast.com`) does not show comments. The
PRD deliberately deferred them: `2026-04-18_django-chat_research.md` lists
"Comment URLs under `/show/comments/`, unless the hosts want public comments"
(line 115) and "Add static/legal/account/comment/Fediverse/API pages only when
there is a Django Chat-specific requirement" (line 726). `AGENTS.md` reinforces
this — do not copy Python Podcast comments "unless a Django Chat-specific
requirement says to do so."

**This spec is that Django Chat-specific requirement.** It turns on the
*upstream django-cast* comment feature and supplies the missing frontend so the
comment UI matches the Django Chat design language. It does **not** copy
Python Podcast-specific styling, routes, or markup.

The investigation behind this spec found that almost everything needed already
ships with django-cast; the gap is purely frontend (templates + CSS).

## What already exists (reused, no new backend code)

django-cast wires the entire comment backend through its `cast.comments` app,
which is already in the installed app stack via `cast.apps`:

- `cast.comments` (before `django_comments`), `threadedcomments`,
  `django_comments` — all active.
- AJAX post view and URLs: `cast.comments.views.post_comment_ajax`, included by
  django-cast at its comments URL prefix; route name
  `comments-post-comment-ajax`.
- Form: `CastCommentForm` (subclasses `ThreadedCommentForm`), excludes
  configured fields, includes a `honeypot` field.
- Spam/moderation: `cast.moderation.Moderator` + `cast.models.SpamFilter`
  (a native NaiveBayes classifier; **not** Akismet — Akismet is not installed).
- Static enhancement asset: `cast/static/fluent_comments/js/ajaxcomments.js`.
- crispy-forms is already installed and configured
  (`crispy_bootstrap4`, `CRISPY_TEMPLATE_PACK = "bootstrap4"` in
  `config/settings/base.py:238-239`) as a transitive django-cast dependency.
  The form *class* imports crispy at module load (its form helper does), so the
  dependency must stay; but this spec renders the form with the site's own
  markup and never calls `{% crispy %}`, so the bootstrap4 pack paints nothing
  user-visible. **No new dependency is added.**

The single gate is the global flag, currently off:

```python
# config/settings/base.py:241
CAST_COMMENTS_ENABLED = False
```

## What is missing (the deliverable)

There are **zero** comment template overrides in the repo, and the default
django-cast / fluent_comments templates assume crispy + Bootstrap markup
(`form-horizontal`, `col-sm-*`). Django Chat is hand-authored custom CSS with
`--dc-*` design tokens and an explicit "no `.btn` system / no Bootstrap" rule
(`docs/css-architecture.md`). So the work is:

1. Two presentation template overrides under `django_chat/templates/comments/`.
2. A `.comment-*` component block in
   `django_chat/static/django_chat/css/site.css`.
3. A comments `<section>` insertion in the episode detail template.
4. Conditional JS + honeypot wiring on the detail page.
5. Documentation + a small CSS-doc reconciliation.

## Product decisions (locked)

| Decision | Choice |
|----------|--------|
| Structure | **Threaded** replies (`threadedcomments` is already installed). |
| Identity | **Anonymous + name/email.** Email is collected but not displayed; `url`/`title` fields excluded from the form. |
| Moderation posture | **Auto-publish + native spam filter.** Predicted ham publishes immediately; predicted spam is hidden. |

## Approach

**Chosen — bespoke presentation overrides + a `.comment-*` block in
`site.css`, keeping the AJAX/structural contract.**

The cast AJAX script (`ajaxcomments.js`) inserts and relocates comments by
querying specific ids/classes (`#comments-{object_id}`, `.comment-list-wrapper`,
`.comment-wrapper`, `#c{comment.id}`, `.comment-reply-link[data-comment-id]`,
`.js-comments-form`, `.comment-waiting`, `.comment-added-message`,
`.comment-cancel-reply-link`). We therefore **keep the structural container
templates** (`fluent_comments/templatetags/threaded_list.html`) and their
classes/ids intact and restyle them with CSS, and override only the two
*presentation* templates whose markup is visible and Bootstrap-flavored.

Rejected alternatives:

- **CSS-only over default templates (the cast-bootstrap5 approach).** The
  default `form.html` renders `{% crispy form %}` with Bootstrap
  `form-horizontal`/`col-sm-*` structure. On a non-Bootstrap site this looks
  wrong and fights `css-architecture.md`.
- **Adopt the cast-bootstrap5 theme.** Pulls Bootstrap 5 into a deliberately
  non-Bootstrap, hand-authored stylesheet — a major regression.

## Template overrides (`django_chat/templates/comments/`)

These override django-cast's defaults by Django's template lookup order.

### `comment.html` (individual comment presentation)

Replaces the default per-comment card with Django Chat markup. Renders:

- author name (linked with `rel="nofollow"` only if `comment.url` is present),
- `comment-date` (localized submit date),
- `comment-text` (body via `|linebreaks`),
- staff-only `comment-moderated-flag` when `not comment.is_public`,
- threaded `comment-reply-link` when `USE_THREADEDCOMMENTS and not preview`.

**Must preserve** (JS/anchor contract): the wrapper `id="c{{ comment.id }}"`
(and `id="comment-preview"` in preview mode), the `comment-reply-link` class
with `data-comment-id="{{ comment.id }}"`, and the `preview` branch.

### `form.html` (comment + reply form)

Replaces `{% crispy form %}` with hand-rolled markup:

- `<form ... class="js-comments-form ..." action="..."
  data-ajax-action="{% url 'comments-post-comment-ajax' %}"
  data-object-id="...">` — keep `js-comments-form` and `data-ajax-action`
  (JS contract).
- Hidden management fields rendered explicitly (`content_type`, `object_pk`,
  `timestamp`, `security_hash`, `parent`), the `honeypot` field, and a `next`
  hidden input for the no-JS redirect target.
- Visible fields: `name`, `email`, `comment` (textarea). No `url`, no `title`.
- Submit + Preview buttons styled as contextual Django Chat links/buttons
  (no new `.btn` taxonomy).
- `{% ajax_comment_tags for form.target_object %}` retained for the cancel-reply
  link, waiting spinner, and success/moderated messages.

### `base.html` (no-JS shell, lower priority — included in slice)

Override so the standalone `preview.html` / `posted.html` pages (reached only on
the no-JS POST path) extend the Django Chat site shell instead of cast's bare
HTML page. Included in this slice but lower-priority: the no-JS path already
functions without it, so it can land last.

## CSS — new `.comment-*` block (`components` layer)

Add a `.comment-*` domain prefix (per `css-architecture.md`'s "pick the most
specific prefix" rule) inside a reopened `@layer components` block in
`site.css`. Rules cover:

- `.comments-section` — the detail-page section wrapper; uses `.stack` for
  vertical rhythm and a top rule (`--dc-line`) to separate from show notes.
- `.comment` — comment card: pale-green/paper surface
  (`--dc-surface-django-tint`), `--dc-radius-card` corner, `--dc-shadow-sm`
  elevation, spacing from the `--s*` scale.
- threaded indentation via the existing `.comment-list-wrapper` /
  `.comment-wrapper` nesting (restyle, do not rename — they are upstream).
- `.comment-date`, `.comment-text`, `.comment-moderated-flag` (small-caps),
  `.comment-reply-link` / `.comment-cancel-reply-link` as contextual links.
- form fields styled with the site's input idiom; `--dc-focus-outline`
  (`outline-offset: 3px`) on all focusables.
- `.comment-waiting`, `.comment-added-message` AJAX feedback.
- honeypot hidden: `#div_id_honeypot { display: none }` (folded into `site.css`
  rather than loading cast's `ajaxcomments.css`, to keep the single-stylesheet
  architecture).

Token discipline: reuse existing `--dc-*` / `--s*` tokens; introduce a new
token only if at least two components share it (per the doc's promotion rule).

## Episode detail integration

Insert a comments section into
`django_chat/templates/cast/django_chat/episode.html` below the show notes.
Exact placement — within `.episode-main` below `.episode-body`, or full-width
below the two-column body/sidebar area — is finalized during implementation and
the local visual review (comments most likely read best full-width below both
columns):

```django
{% if comments_are_enabled %}
  <section class="comments-section stack" id="comments">
    <h2 class="show-notes-title">Comments</h2>
    {% render_comment_list for page %}
    {% render_comment_form for page %}
  </section>
{% endif %}
```

`comments_are_enabled` is already provided in the page context by django-cast
(`cast/models/pages.py`), and `post.html` inherits this template via
`{% extends "./episode.html" %}`, so episodes and posts both get comments.

`{% load comments %}` is added at the top of the template, and the cast AJAX
script is loaded conditionally in the page's JavaScript block:

```django
{% if comments_are_enabled %}
  <script defer src="{% static 'fluent_comments/js/ajaxcomments.js' %}"></script>
{% endif %}
```

## No-JS and AJAX behavior

The JS is **pure progressive enhancement**, consistent with the repo's
"JS adds polish, not access" contract:

- **JS on:** inline AJAX post, threaded reply-form relocation, inline preview,
  inline validation errors, scroll-to-new-comment.
- **JS off:** the form does a normal POST to the django-comments endpoint →
  `posted.html` → redirect back to the page anchor. Reply still works as a
  full-page round trip via the `parent` field.

Both paths must be verified.

## Spam and moderation

Uses django-cast's native machinery, no external service:

- `cast.moderation.Moderator.allow()` always accepts the comment into the
  database; `moderate()` runs `SpamFilter.get_default().model.predict_label()`
  on the comment message. `"spam"` → `is_removed=True, is_public=False`
  (hidden); otherwise `is_public=True` (auto-published immediately).
- The `honeypot` field adds a cheap bot trap on top of the classifier.
- With no trained `SpamFilter` row, `moderate()` degrades to "unknown" → public.

### Spam-filter seeding (pre-launch ops follow-up, out of scope here)

Training material already exists in `../python-podcast` (a comment corpus of
labeled ham/spam). django-cast trains *from the comments table itself*:

- `SpamFilter.get_training_data_comments()` labels every existing comment
  (`ham` if public and not removed, else `spam`) into `(label, message)` pairs.
- `SpamFilter.retrain_from_scratch(train)` fits a `NaiveBayes`, stores the
  serialized model + precision/recall/f1, and saves.

So seeding Django Chat is: **import python-podcast's comments into Django
Chat's comments table, then run a one-off retrain.** python-podcast runs
Postgres; this is a data export/import + retrain ops step. It is recommended
before a real public launch but is **not** part of the template/CSS slice —
untrained, the site simply auto-publishes everything (acceptable for an initial
staging switch-on).

## Enablement chain (documented, not all flipped by this slice)

`comments_are_enabled` resolves to:

```
CAST_COMMENTS_ENABLED (settings)
  AND blog.comments_enabled   (Wagtail admin, per Podcast/Blog)
  AND post.comments_enabled   (Wagtail admin, per Episode/Post)
```

Turning comments on for staging therefore requires:

1. `CAST_COMMENTS_ENABLED = True` in settings (and per-environment as desired).
2. `comments_enabled = True` on the Podcast/Blog page in Wagtail admin.
3. `comments_enabled = True` on the episodes/posts that should accept comments.

The implementation slice flips the global flag in the appropriate settings
layer; the per-object toggles are an operator action documented in
`docs/local-development.md` and the host/operations docs.

## Local verification plan

The user expects to test templates against a running dev server.

1. `just runserver-local-media` against the populated `db.sqlite3`
   (filesystem media; no staging secrets needed).
2. Set `CAST_COMMENTS_ENABLED = True` (local settings) and toggle
   `comments_enabled` on the imported podcast + a test episode in Wagtail admin.
3. Load an episode detail page and verify:
   - the comments section renders below show notes and above/with the sidebar;
   - posting a comment (JS on) inserts it inline and auto-publishes;
   - a threaded reply relocates the form and nests correctly;
   - preview renders inline;
   - posting with JS disabled round-trips through `posted.html` and returns;
   - the honeypot field is hidden and a filled honeypot is rejected;
   - a comment the (optionally seeded) `SpamFilter` predicts as spam is hidden
     from anonymous users and flagged for staff.

Screenshots saved under `.playwright-verify/` per repo convention.

## Design-doc reconciliation (the doc-freshness question)

A spot check of `docs/css-architecture.md` against `site.css` (4933 lines)
found the doc is an accurate, reliable build guide — layer order
(`@layer base, components, modals;`), `--dc-*` token prefixing, and class-naming
conventions all match the implementation. Drift found and its disposition:

- `--dc-radius-card` (`0.75rem`, the card/panel corner — directly relevant to
  the comment card) existed in `site.css:149` but was **not** listed in the
  doc's geometry-token section. **Resolved separately** in commit `e83e6f4`,
  which also added `--dc-container-max` and a radius-scale gloss.
- Add the new `.comment-*` domain prefix to the class-naming section (still
  pending; handled by the implementation plan's CSS task).

(A fuller token-by-token doc/CSS audit is not warranted; the doc is otherwise
current.)

## Tests and quality gates

- A template/render test: the comments section appears when
  `comments_are_enabled` is true and is absent when false; the form carries the
  `js-comments-form` class and the AJAX action URL.
- Optional Playwright check that the section renders on an episode page with
  comments enabled.
- Run `just test` and the configured hook runner (`prek`/`pre-commit`) before
  considering the slice complete.
- Update `docs/implementation-status.md` (Open Work item → shipped) and
  `docs/css-architecture.md` (the two reconciliation edits above).

## Out of scope (YAGNI)

- Comment counts / "N comments" badges on list and index pages.
- Email notifications on new comments or replies.
- A user-account / login-based comment flow (the site has no public signup).
- A Wagtail UI for managing/training the spam model.
- Importing historical comments as content (distinct from the spam-training
  corpus import, which is an ops follow-up).
- Akismet or any external spam service.

## Open questions / follow-ups

- **Spam-filter seeding** before public launch (ops): import python-podcast's
  labeled corpus and `retrain_from_scratch`. Tracked as a follow-up, not this
  slice.
- **Per-object default**: decide whether newly imported episodes should default
  `comments_enabled` on or off (recommend: off by default; opt-in per episode,
  or globally via the blog toggle).

## Key references (absolute-ish paths)

- Gate: `config/settings/base.py:241` (`CAST_COMMENTS_ENABLED`).
- crispy config: `config/settings/base.py:238-239`.
- Episode template: `django_chat/templates/cast/django_chat/episode.html`.
- Stylesheet: `django_chat/static/django_chat/css/site.css`.
- CSS guide: `docs/css-architecture.md`.
- Upstream backend: `cast.comments` (views/urls/forms),
  `cast.moderation.Moderator`, `cast.models.SpamFilter`,
  `cast.models.pages` (`comments_are_enabled` chain).
- Upstream JS: `cast/static/fluent_comments/js/ajaxcomments.js`.
- Reference implementations (do not copy verbatim):
  `../python-podcast` (default cast templates + minimal CSS),
  `../cast-bootstrap5` (Bootstrap 5 SCSS theme; informs CSS hooks only).
