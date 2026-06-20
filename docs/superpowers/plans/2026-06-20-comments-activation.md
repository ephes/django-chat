# Comments Activation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn on django-cast comments for Django Chat episodes/posts with bespoke templates and CSS that match the site's design language.

**Architecture:** The django-cast comment backend (`cast.comments` + `threadedcomments` + native `SpamFilter`/`Moderator`) is already installed; the work is (1) mounting the comment URLs, (2) replacing the two Bootstrap/crispy presentation templates with Django-Chat markup, (3) wiring a comments section into the episode template behind an env-driven flag, and (4) styling it with a new `.comment-*` block in the single hand-authored `site.css`. The cast AJAX script is loaded as pure progressive enhancement; the no-JS POST path keeps working.

**Tech Stack:** Django, Wagtail, django-cast, `django_comments` + `threadedcomments`, pytest, hand-authored CSS (cascade layers + `--dc-*` tokens), `uv`/`just`.

**Spec:** `docs/superpowers/specs/2026-06-20-comments-activation-design.md`

## Global Constraints

- **Reuse the upstream backend.** Do not reimplement comment models/views/forms; only mount URLs, override templates, add CSS, and flip the flag.
- **Preserve the AJAX/anchor contract classes/ids** (the cast `ajaxcomments.js` queries them): form `js-comments-form` + `data-ajax-action`; comment wrapper `id="c{{comment.id}}"` / `id="comment-preview"`; `comment-reply-link` + `data-comment-id`; the hidden `parent` field with its default `id="id_parent"`; `comment-list-wrapper` / `comment-wrapper` from `threaded_list.html` (do **not** override that template); `comment-waiting` / `comment-added-message` / `comment-cancel-reply-link` from `{% ajax_comment_tags %}`.
- **Design language:** custom CSS only — no Bootstrap, no preprocessor. Use `--dc-*` / `--s*` / `--text-*` tokens. Do **not** introduce a `.btn` taxonomy (reuse `.button-primary`; style a contextual `.comment-preview-button`). Do **not** rename `cast-*` classes. Browser floor iOS/Safari 16+; pair `color-mix()` with `rgb()` fallback only where it paints a visible surface that must work on 16.0/16.1.
- **JS adds polish, not access.** The form must work with JS disabled (normal POST → `posted.html` → redirect).
- **Quality gates before "done":** `just test` green and the configured hook runner (`prek`/`pre-commit`) passing. Update docs in the same change.
- **Git:** trunk-based on `main`. This plan's per-task `git commit` steps are its intended workflow — choosing to execute the plan authorizes those scoped, per-task commits, so run them as written. Do **not** `git push` and do **not** run destructive git commands. Commits must not reference yourself/Anthropic, must not add generated-by watermarks, and must each be one logical change. (If you are executing this plan without commit authorization, stage each task's files instead and let the operator commit.)
- **Secrets:** never commit secrets.

---

## File Structure

- **Create:** `django_chat/templates/comments/comment.html` — single-comment presentation (Django Chat card markup).
- **Create:** `django_chat/templates/comments/form.html` — crispy-free comment/reply form.
- **Create:** `django_chat/templates/comments/base.html` — no-JS shell so `preview.html`/`posted.html` use the site chrome (lower-priority).
- **Create:** `django_chat/core/tests/test_comments.py` — comment tests.
- **Modify:** `config/urls.py` — mount `cast.comments.urls`.
- **Modify:** `config/settings/base.py:241` — make `CAST_COMMENTS_ENABLED` env-driven.
- **Modify:** `django_chat/templates/cast/django_chat/episode.html` — comments section + conditional AJAX script + `{% load comments %}`.
- **Modify:** `django_chat/static/django_chat/css/site.css` — append a reopened `@layer components` block with `.comment-*` rules.
- **Modify:** `django_chat/templates/cast/django_chat/base.html` — bump the `site.css` cache-bust `?v=`.
- **Modify:** `.env.example` — document `CAST_COMMENTS_ENABLED`.
- **Modify:** `docs/local-development.md` — how to enable comments locally + per-episode opt-out.
- **Modify:** `docs/css-architecture.md` — document `--dc-radius-card` and the `.comment-*` prefix.
- **Modify:** `docs/implementation-status.md` — flip Open Work item 7 to in-progress/shipped.

---

## Task 1: Mount comment URLs

Without this, `{% url 'comments-post-comment-ajax' %}` and `{% comment_form_target %}` raise `NoReverseMatch` and any comment render 500s. `cast.urls` does **not** include the comment URLs in this project (verified: all three names fail to reverse today).

**Files:**
- Modify: `config/urls.py`
- Test: `django_chat/core/tests/test_comments.py` (create)

**Interfaces:**
- Produces (for later tasks): reversible URL names `comments-post-comment-ajax` (cast AJAX endpoint) and `comments-post-comment` / `comments-comment-done` (from `django_comments.urls`), all mounted under the `comments/` prefix (e.g. `/comments/post/ajax/`).

- [ ] **Step 1: Write the failing test**

Create `django_chat/core/tests/test_comments.py`:

```python
from __future__ import annotations

import pytest
from django.urls import NoReverseMatch, reverse


def test_comment_urls_are_mounted() -> None:
    # Enabling comments renders templates that reverse these names; if they are
    # not mounted, an enabled comment page 500s.
    assert reverse("comments-post-comment-ajax") == "/comments/post/ajax/"
    # The no-JS POST path needs the standard django_comments post + done URLs
    # (post -> redirect to the "comment posted" page). A misconfigured include
    # could mount the AJAX endpoint but omit these, so assert each explicitly.
    for name in ("comments-post-comment", "comments-comment-done"):
        try:
            reverse(name)
        except NoReverseMatch:  # pragma: no cover - failure path
            pytest.fail(f"django_comments URL {name!r} is not included under comments/")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `just manage test 2>/dev/null; uv run pytest django_chat/core/tests/test_comments.py::test_comment_urls_are_mounted -v`
Expected: FAIL with `NoReverseMatch` for `comments-post-comment-ajax`.

- [ ] **Step 3: Mount the URLs**

In `config/urls.py`, add the include **before** the `cast.urls` / wagtail catch-all includes (currently lines 66-67, both at prefix `""`). Insert after the existing explicit includes (e.g. after the `documents/` line):

```python
    path("comments/", include("cast.comments.urls")),
```

Ensure `include` is imported (it is already used in this file). The route order matters: it must precede `path("", include(wagtail_urls))` so Wagtail's catch-all does not swallow it.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest django_chat/core/tests/test_comments.py::test_comment_urls_are_mounted -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add config/urls.py django_chat/core/tests/test_comments.py
git commit -m "Mount cast.comments URLs so comment templates can reverse"
```

---

## Task 2: Crispy-free templates + episode integration + env flag

Replace the two Bootstrap/crispy presentation templates with Django-Chat markup, wire a comments section into the episode template, and make the global flag env-driven (default off; staging opts in). Both `Blog.comments_enabled` and `Post.comments_enabled` default to `True` upstream, so the global flag is the effective gate; per-episode is an admin opt-*out*.

**Files:**
- Create: `django_chat/templates/comments/comment.html`
- Create: `django_chat/templates/comments/form.html`
- Modify: `config/settings/base.py:241`
- Modify: `django_chat/templates/cast/django_chat/episode.html`
- Modify: `.env.example`
- Modify: `docs/local-development.md`
- Test: `django_chat/core/tests/test_comments.py`

**Interfaces:**
- Consumes: the URL names from Task 1.
- Produces: an episode page that renders `<section class="comments-section">` with `{% render_comment_list %}` + `{% render_comment_form %}` when `comments_are_enabled`; the form carries `js-comments-form`, `data-ajax-action`, visible `name`/`email`/`comment` fields, a hidden `honeypot`, and the cast AJAX script is loaded. CSS classes produced for Task 3 to style: `.comments-section`, `.comments-title`, `.comment`, `.comment-meta`, `.comment-author`, `.comment-date`, `.comment-moderated-flag`, `.comment-reply-link`, `.comment-text`, `.comment-form`, `.comment-field`, `.comment-field--honeypot`, `.comment-field--error`, `.js-errors`, `.comment-form-actions`, `.comment-preview-button`, `.comments-closed`.

- [ ] **Step 1: Write the failing tests**

Append to `django_chat/core/tests/test_comments.py`:

```python
from django.conf import settings
from django.test import Client, override_settings

from django_chat.imports.import_sample import import_django_chat_sample

EPISODE_SLUG = "django-tasks-jake-howard"


def _episode_detail_path() -> str:
    return f"/{settings.DJANGO_CHAT_PODCAST_SLUG}/{EPISODE_SLUG}/"


@pytest.mark.django_db
def test_comments_section_absent_when_flag_disabled(client: Client) -> None:
    import_django_chat_sample()
    content = client.get(_episode_detail_path()).content.decode()
    assert 'class="comments-section' not in content
    assert "js-comments-form" not in content
    assert "fluent_comments/js/ajaxcomments.js" not in content


@pytest.mark.django_db
@override_settings(CAST_COMMENTS_ENABLED=True)
def test_comments_section_renders_django_chat_markup_when_enabled(client: Client) -> None:
    import_django_chat_sample()
    response = client.get(_episode_detail_path())
    assert response.status_code == 200  # not a 500 from a missing reverse
    content = response.content.decode()
    # Section + JS/AJAX contract preserved
    assert 'class="comments-section' in content
    assert 'class="js-comments-form' in content
    assert 'data-ajax-action="/comments/post/ajax/"' in content
    assert "fluent_comments/js/ajaxcomments.js" in content
    # Our crispy-free fields
    assert 'name="name"' in content
    assert 'name="email"' in content
    assert 'name="comment"' in content
    assert 'name="honeypot"' in content
    # Bootstrap/crispy markup is gone (proves the override replaced the default)
    assert "form-horizontal" not in content
    assert "col-sm-" not in content
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest django_chat/core/tests/test_comments.py -v`
Expected: `test_comments_section_absent_when_flag_disabled` PASSES (nothing wired yet); `test_comments_section_renders_django_chat_markup_when_enabled` FAILS (no `comments-section` in output). If the enabled test 500s instead, that is also a failure to fix here.

- [ ] **Step 3: Create `comments/comment.html`**

Create `django_chat/templates/comments/comment.html`:

```django
{% load i18n %}
<div{% if preview %} id="comment-preview"{% else %} id="c{{ comment.id }}"{% endif %} class="comment">
  {% block comment_item %}
    {% if preview %}<p class="comment-preview-label">{% trans "Preview of your comment" %}</p>{% endif %}
    <p class="comment-meta">
      <span class="comment-author">{% if comment.url %}<a href="{{ comment.url }}" rel="nofollow">{% endif %}{% if comment.name %}{{ comment.name }}{% else %}{% trans "Anonymous" %}{% endif %}{% if comment.url %}</a>{% endif %}</span>
      <time class="comment-date" datetime="{{ comment.submit_date|date:'c' }}">{% blocktrans with submit_date=comment.submit_date %}on {{ submit_date }}{% endblocktrans %}</time>
      {% if request.user.is_staff and not comment.is_public %}<span class="comment-moderated-flag">({% trans "moderated" %})</span>{% endif %}
      {% if USE_THREADEDCOMMENTS and not preview %}<a href="#c{{ comment.id }}" data-comment-id="{{ comment.id }}" class="comment-reply-link">{% trans "reply" %}</a>{% endif %}
    </p>
    <div class="comment-text">{{ comment.comment|linebreaks }}</div>
  {% endblock %}
</div>
```

- [ ] **Step 4: Create `comments/form.html`**

Create `django_chat/templates/comments/form.html` (renders fields manually — no `{% crispy %}`; keeps the JS contract; includes `{% csrf_token %}` for the no-JS POST):

```django
{% load i18n comments fluent_comments_tags %}

{% if not form.target_object|comments_are_open %}
  <p class="comments-closed">{% trans "Comments are closed." %}</p>
{% else %}
  <form id="comment-form-{{ form.target_object.pk }}"
        class="js-comments-form comment-form stack"
        method="post"
        action="{% comment_form_target %}"
        data-object-id="{{ form.target_object.pk }}"
        data-ajax-action="{% url 'comments-post-comment-ajax' %}">
    {% csrf_token %}
    {% with next_url=next|default:request.get_full_path %}
      {% if next_url %}<input type="hidden" name="next" value="{{ next_url }}">{% endif %}
    {% endwith %}

    {% for field in form %}
      {% if field.is_hidden %}
        {{ field }}
      {% elif field.name == "honeypot" %}
        <div class="comment-field comment-field--honeypot" aria-hidden="true">{{ field.label_tag }}{{ field }}</div>
      {% else %}
        <div class="comment-field{% if field.errors %} comment-field--error{% endif %}">
          {{ field.label_tag }}
          {{ field }}
          {% if field.errors %}<span class="js-errors">{{ field.errors.as_text }}</span>{% endif %}
        </div>
      {% endif %}
    {% endfor %}

    <div class="comment-form-actions cluster">
      <button type="submit" name="post" value="post" class="button-primary">{% trans "Post comment" %}</button>
      <button type="submit" name="preview" value="preview" class="comment-preview-button">{% trans "Preview" %}</button>
      {% ajax_comment_tags for form.target_object %}
    </div>
  </form>
{% endif %}
```

Note on the submit buttons: both views detect preview by **key presence**
(`"preview" in data` — `django_comments/views/comments.py` and
`cast/comments/views.py`), and the AJAX script keys off the submitter's *name*,
so preview works regardless of the button value. The explicit `value="post"` /
`value="preview"` match upstream's own templates and remove any ambiguity.

- [ ] **Step 5: Make the flag env-driven**

In `config/settings/base.py`, replace line 241:

```python
CAST_COMMENTS_ENABLED = False
```

with:

```python
CAST_COMMENTS_ENABLED = env.bool("CAST_COMMENTS_ENABLED", default=False)
```

(`env = environ.Env()` already exists at the top of the file; `env.bool(..., default=...)` is the established idiom.)

- [ ] **Step 6: Wire the comments section into the episode template**

In `django_chat/templates/cast/django_chat/episode.html`:

a) Add to the load block near the top (after line 6, `{% load dc_filters %}`):

```django
{% load comments %}
```

b) Insert the comments section after the `</article>` close and before the closing `</div>` of `#episode-detail-main` (between the current lines 83 and 84):

```django
    </article>

    {% if comments_are_enabled %}
      <section class="comments-section stack" id="comments" aria-label="Comments">
        <h2 class="comments-title">Comments</h2>
        {% render_comment_list for page %}
        {% render_comment_form for page %}
      </section>
    {% endif %}
  </div>
```

c) Add the AJAX enhancement script to the `{% block javascript %}` (after the `vite_asset` block, before `{% endblock javascript %}`):

```django
  {% if comments_are_enabled %}
    <script defer src="{% static 'fluent_comments/js/ajaxcomments.js' %}"></script>
  {% endif %}
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `uv run pytest django_chat/core/tests/test_comments.py -v`
Expected: all PASS. If the enabled test fails because the flag did not take effect under `override_settings`, confirm `cast.comments.appsettings` reads `settings.CAST_COMMENTS_ENABLED` dynamically (it does, via module `__getattr__`); a failure here means the page context cached it — re-check `comments_are_enabled` resolution.

- [ ] **Step 8: Update `.env.example` and local-dev docs**

In `.env.example`, add (near other Django Chat flags):

```bash
# Enable django-cast comments on episode/post pages (default off). Set to true
# per-environment to switch comments on (e.g. on staging).
CAST_COMMENTS_ENABLED=false
```

In `docs/local-development.md`, add a short "Comments" subsection:

```markdown
## Comments

Comments are off by default. To exercise them locally:

1. Set `CAST_COMMENTS_ENABLED=true` in your `.env` (or export it) and restart
   `just runserver-local-media`.
2. Comments are then on for every episode/post (django-cast defaults each
   page's `comments_enabled` to true). To turn them off for a specific
   episode, uncheck **comments_enabled** on that page in the Wagtail admin.

With JavaScript enabled, posting is AJAX (inline, threaded replies, preview).
With JavaScript disabled, the form does a normal POST and redirects back.
Spam handling uses django-cast's native `SpamFilter` (auto-publish + honeypot);
seeding a trained filter from the python-podcast corpus is a separate
pre-launch ops step.
```

- [ ] **Step 9: Commit**

```bash
git add config/settings/base.py config/urls.py \
  django_chat/templates/comments/comment.html \
  django_chat/templates/comments/form.html \
  django_chat/templates/cast/django_chat/episode.html \
  django_chat/core/tests/test_comments.py .env.example docs/local-development.md
git commit -m "Render Django Chat comment templates on episode pages behind env flag"
```

---

## Task 3: Style the `.comment-*` component

Add the bespoke CSS and bust the stylesheet cache. CSS visual styling is verified in the browser (no pytest unit test for appearance), per the spec's local verification plan.

**Files:**
- Modify: `django_chat/static/django_chat/css/site.css` (append)
- Modify: `django_chat/templates/cast/django_chat/base.html` (cache-bust)
- Modify: `docs/css-architecture.md` (reconciliation)

**Interfaces:**
- Consumes: the classes produced by Task 2.

- [ ] **Step 1: Append the `.comment-*` block to `site.css`**

Append at the end of `django_chat/static/django_chat/css/site.css` (after `} /* end @layer modals */`). The layer order is fixed at the top of the file (`@layer base, components, modals;`), so reopening `components` here slots correctly regardless of file position:

```css
/* Comments — reopened components layer (cascade order fixed at top of file). */
@layer components {
  .comments-section {
    --stack-space: var(--s2);
    margin-top: var(--s3);
    padding-top: var(--s2);
    border-top: 1px solid var(--dc-line);
  }

  .comments-title {
    font-family: var(--font-heading);
    font-size: var(--text-h2);
    line-height: var(--leading-heading);
    color: var(--dc-heading);
  }

  .comment-list-wrapper {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: var(--s1);
  }
  .comment-list-wrapper .comment-list-wrapper {
    margin-top: var(--s1);
    margin-left: var(--s1);
    padding-left: var(--s1);
    border-left: 2px solid var(--dc-line);
  }
  .comment-wrapper { list-style: none; }

  .comment {
    background: var(--dc-surface-django-tint);
    border: 1px solid var(--dc-line);
    border-radius: var(--dc-radius-card);
    box-shadow: var(--dc-shadow-sm);
    padding: var(--s1) clamp(1rem, 2.5vw, 1.5rem);
  }
  .comment-preview-label {
    margin: 0 0 var(--s-1);
    font-size: var(--text-sm);
    color: var(--dc-muted);
  }

  .comment-meta {
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    gap: var(--s-1);
    margin: 0 0 var(--s-1);
    font-size: var(--text-sm);
  }
  .comment-author { font-weight: var(--weight-semibold); color: var(--dc-heading); }
  .comment-date { color: var(--dc-muted); }
  .comment-moderated-flag { color: var(--dc-error); font-variant: small-caps; }
  .comment-reply-link { margin-left: auto; color: var(--dc-django-aaa); }

  .comment-text { color: var(--dc-ink); }
  .comment-text > :first-child { margin-top: 0; }
  .comment-text > :last-child { margin-bottom: 0; }

  .comment-form { --stack-space: var(--s1); max-width: var(--dc-measure); }
  .comment-field { display: flex; flex-direction: column; gap: var(--s-2); }
  .comment-field label { font-weight: var(--weight-medium); font-size: var(--text-sm); }
  .comment-field input,
  .comment-field textarea {
    width: 100%;
    padding: var(--s-1) var(--s0);
    font: inherit;
    color: var(--dc-ink);
    background: var(--dc-paper);
    border: 1px solid var(--dc-line);
    border-radius: var(--dc-radius);
  }
  .comment-field textarea { min-height: 8rem; resize: vertical; }
  .comment-field input:focus-visible,
  .comment-field textarea:focus-visible {
    outline: var(--dc-focus-outline);
    outline-offset: 3px;
  }
  .comment-field--honeypot { display: none; }
  .comment-field--error input,
  .comment-field--error textarea { border-color: var(--dc-error); }
  .js-errors { color: var(--dc-error); font-size: var(--text-sm); }

  .comment-form-actions { --cluster-space: var(--s0); align-items: center; }
  .comment-preview-button {
    display: inline-flex;
    align-items: center;
    padding: var(--s-1) var(--s0);
    border: 1px solid var(--dc-line);
    border-radius: var(--dc-radius-pill);
    background: transparent;
    color: var(--dc-ink);
    cursor: pointer;
  }
  .comment-waiting { color: var(--dc-muted); font-size: var(--text-sm); }
  .comment-added-message { color: var(--dc-django-aaa); }
  .comment-cancel-reply-link { color: var(--dc-muted); }
  .js-comments-form-orig-position .comment-cancel-reply-link { display: none; }
  .comments-closed { color: var(--dc-muted); }
}
```

- [ ] **Step 2: Bust the stylesheet cache**

In `django_chat/templates/cast/django_chat/base.html` line 68, bump the query string so browsers fetch the new CSS:

```django
    <link rel="stylesheet" href="{% static 'django_chat/css/site.css' %}?v=comments-1">
```

- [ ] **Step 3: Verify in the browser**

Run the dev server against the populated dev DB and confirm styling. (Range requests / `?t=` deep links are irrelevant here.)

Run:
```bash
CAST_COMMENTS_ENABLED=true just runserver-local-media
```
Then load `http://localhost:8000/episodes/django-tasks-jake-howard/` and confirm:
- the Comments section renders below the show notes with the top rule and heading;
- the form fields and Post/Preview buttons match the site (green primary button, focus rings);
- the honeypot field is not visible;
- posting a comment inserts it inline as a styled card; a reply nests/indents;
- Preview renders inline.

Capture before/after screenshots into `.playwright-verify/` per repo convention (desktop + mobile widths).

- [ ] **Step 4: Reconcile `docs/css-architecture.md`**

Two edits:

a) In the **Token naming → Geometry** bullet, add `--dc-radius-card` to the list, e.g. change `` `--dc-radius`, `--dc-radius-pill`, `--dc-tap`, …`` to include `` `--dc-radius-card` `` with a short note "(12px card/panel corner)".

b) In **Class naming → Domain prefixes**, add a bullet:

```markdown
- `.comment-*` — comment list, comment cards, and the comment/reply form.
```

- [ ] **Step 5: Commit**

```bash
git add django_chat/static/django_chat/css/site.css \
  django_chat/templates/cast/django_chat/base.html docs/css-architecture.md
git commit -m "Style comments to the Django Chat design language; document tokens"
```

---

## Task 4: No-JS shell for preview/posted pages (lower priority)

So the standalone `preview.html` / `posted.html` pages (reached only when JS is off) render inside the site chrome instead of cast's bare system-ui page. Lower priority — the no-JS path already functions without this.

**Files:**
- Create: `django_chat/templates/comments/base.html`
- Test: `django_chat/core/tests/test_comments.py`

- [ ] **Step 1: Write the failing test**

Append to `django_chat/core/tests/test_comments.py`:

```python
from django.template.loader import render_to_string


def test_comment_posted_page_uses_site_shell() -> None:
    # preview.html/posted.html extend comments/base.html; our override makes
    # that the Django Chat site shell instead of cast's bare page.
    html = render_to_string("comments/posted.html", {"next": "/episodes/"})
    assert 'class="site-header"' in html
    assert "Django Chat" in html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest django_chat/core/tests/test_comments.py::test_comment_posted_page_uses_site_shell -v`
Expected: FAIL (default `comments/base.html` is cast's bare page; no `site-header`).

- [ ] **Step 3: Create the override**

Create `django_chat/templates/comments/base.html`:

```django
{% extends "cast/django_chat/base.html" %}
```

`preview.html` / `posted.html` fill `{% block content %}` and `{% block title %}`, which the site base already defines; the site base guards all page-specific context (`page`, `podcast`, `source_metadata`) with `{% if %}`, so the standalone pages render without those.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest django_chat/core/tests/test_comments.py::test_comment_posted_page_uses_site_shell -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add django_chat/templates/comments/base.html django_chat/core/tests/test_comments.py
git commit -m "Render no-JS comment preview/posted pages in the site shell"
```

---

## Task 5: Full verification, status doc, quality gates

**Files:**
- Modify: `docs/implementation-status.md`

- [ ] **Step 1: Run the full test suite**

Run: `just test`
Expected: all green, including `django_chat/core/tests/test_comments.py`.

- [ ] **Step 2: Run the configured hooks**

Check which runner is configured (`prek.toml` exists), then run it. Run: `prek run --all-files` (or `pre-commit run --all-files` if that is what is configured).
Expected: pass (ruff lint/format, ty typecheck, etc.).

- [ ] **Step 3: Manual end-to-end verification (no-JS + AJAX + spam-hide)**

With `CAST_COMMENTS_ENABLED=true just runserver-local-media`, confirm the full spec checklist:
- comments section renders below show notes; absent when the flag is off;
- JS on: post (auto-publishes), threaded reply, inline preview, scroll-to-new;
- JS off (disable in devtools): the form POSTs, lands on the posted page in the site shell, and redirects back;
- the honeypot field is hidden, and a submission with the honeypot filled is rejected;
- (optional) seed a `SpamFilter` and confirm a spam-predicted comment is hidden from anonymous users and flagged for staff.

Note any deviations; fix or record as follow-ups.

- [ ] **Step 4: Update the status doc**

In `docs/implementation-status.md`, update Open Work item 7 ("Activate comments…") to reflect what shipped (templates + CSS + env flag + URL mount + no-JS shell), note that staging is enabled by setting `CAST_COMMENTS_ENABLED=true`, and that spam-filter seeding from the python-podcast corpus remains a pre-launch ops follow-up.

- [ ] **Step 5: Commit**

```bash
git add docs/implementation-status.md
git commit -m "Record comments activation in implementation status"
```

---

## Self-Review

**Spec coverage:**
- Reuse upstream backend → Tasks 1-2 (mount URLs, no backend rewrite). ✓
- Two presentation template overrides (`comment.html`, `form.html`) → Task 2. ✓
- `.comment-*` CSS block in `site.css` → Task 3. ✓
- Comments section in `episode.html` + conditional JS + honeypot → Task 2. ✓
- No-JS path holds; `base.html` shell override → Task 4. ✓
- Spam = native `SpamFilter` auto-publish; seeding from python-podcast = ops follow-up (out of scope) → documented in Tasks 2 & 5, not built. ✓
- Enablement chain (env flag + per-object) → Task 2 (env-driven flag; per-object defaults documented). ✓
- Local verification plan → Tasks 3 & 5. ✓
- Design-doc reconciliation (`--dc-radius-card`, `.comment-*`) → Task 3. ✓
- Tests + quality gates + docs → Tasks 1-5. ✓
- Out-of-scope items (counts, email, accounts, Akismet, historical import) → not planned. ✓

**Placeholder scan:** No TBD/TODO; every code step shows complete content. ✓

**Type/name consistency:** URL name `comments-post-comment-ajax` and prefix `/comments/post/ajax/` consistent across Tasks 1-2; CSS class names produced in Task 2 match those styled in Task 3; `comments_are_enabled` (context var) vs `CAST_COMMENTS_ENABLED` (setting) used correctly. ✓

**Deviation from spec resolved during planning:** the spec listed "per-object default" as open; this plan keeps the upstream default (`True`) and controls rollout via an **env-driven** global flag (default off) — no migration, staging opts in. The URL-mount gap (not in the spec) was discovered during planning and added as Task 1.
