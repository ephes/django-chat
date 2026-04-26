# Visual Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring staging into spirit-level parity with djangochat.com — palette, typography, hero, single-column episode rows — and add filterset-driven search/facets, the Podlove player (facade mode), favicon, and OG metadata, all in one bundled change.

**Architecture:** All work lives in `django_chat/` — templates under `django_chat/templates/cast/django_chat/`, the project view at `django_chat/core/views.py`, CSS at `django_chat/static/django_chat/css/site.css`, fonts at `django_chat/static/fonts/`. The custom `podcast_episode_index` view is extended (not replaced) to wire `cast.filters.PostFilterset` and pagination. Podlove is rendered by including django-cast's prebuilt `cast/audio/audio.html` partial; the JS init module is loaded via `django-vite` against the manifest already shipped in the django-cast package. No new Python deps; no Node toolchain.

**Tech Stack:** Django + Wagtail + django-cast (already installed), `django-filter` (transitive via cast), `django-vite` (transitive via cast), Roboto / Roboto Flex / Roboto Mono self-hosted, pytest + pytest-django.

**Spec:** `docs/superpowers/specs/2026-04-26-visual-polish-design.md`. Read it before starting any task.

**Commit policy:** This repo's `AGENTS.md` requires explicit user approval for each `git commit`. Each task ends with a "Stage" step that runs `git add` and `git status --short`, plus a "Suggested commit message (commit only when the user explicitly approves)" line. Do not run `git commit` until the user says so. Do not run `git push` at any point during this plan.

---

## File Structure

**New files**

- `django_chat/static/fonts/Roboto-Variable.woff2`
- `django_chat/static/fonts/RobotoFlex-Variable.woff2`
- `django_chat/static/fonts/RobotoMono-Variable.woff2`
- `django_chat/static/django_chat/favicon.ico`
- `django_chat/static/django_chat/favicon.svg`
- `django_chat/static/django_chat/apple-touch-icon.png`
- `django_chat/static/django_chat/og-image.png`
- `django_chat/templates/cast/django_chat/_filter_form.html`
- `django_chat/templates/cast/django_chat/_meta.html` (OG/Twitter defaults)
- `django_chat/core/templatetags/__init__.py`
- `django_chat/core/templatetags/dc_filters.py`
- `django_chat/core/tests/test_dc_filters.py`
- `django_chat/core/tests/test_episode_index_filter.py`
- `django_chat/core/tests/test_episode_pagination.py`
- `django_chat/core/tests/test_template_meta.py`

**Modified files**

- `django_chat/static/django_chat/css/site.css` (rewrite)
- `django_chat/templates/cast/django_chat/base.html`
- `django_chat/templates/cast/django_chat/blog_list_of_posts.html`
- `django_chat/templates/cast/django_chat/episode.html`
- `django_chat/templates/cast/django_chat/pagination.html` (style only — interface preserved)
- `django_chat/templates/cast/django_chat/400.html`
- `django_chat/templates/cast/django_chat/403.html`
- `django_chat/templates/cast/django_chat/403_csrf.html`
- `django_chat/templates/cast/django_chat/404.html`
- `django_chat/templates/cast/django_chat/500.html`
- `django_chat/core/views.py`
- `config/settings/base.py` (add `CAST_FILTERSET_FACETS`)
- `django_chat/imports/tests/test_sample_site_routes.py` (assertions for new markup)
- `docs/implementation-status.md` (close out the next-action item)

---

## Task 1: Pin design tokens in `site.css`

**Files:**
- Modify: `django_chat/static/django_chat/css/site.css`

- [ ] **Step 1: Rewrite `site.css` with the new tokens, palette, type stack, and shared chrome**

Open `django_chat/static/django_chat/css/site.css` and replace the entire contents with:

```css
:root {
  --dc-ink: #0d0d0d;
  --dc-paper: #ffffff;
  --dc-muted: #5d6673;
  --dc-line: #ececec;
  --dc-link: #0e7c7b;
  --dc-django: #44b78b;
  --dc-radius: 4px;
  --dc-container: min(1120px, 100% - 32px);
}

*,
*::before,
*::after {
  box-sizing: border-box;
}

html {
  -webkit-font-smoothing: antialiased;
  text-size-adjust: 100%;
}

body {
  margin: 0;
  background: var(--dc-paper);
  color: var(--dc-ink);
  font-family: "Roboto", system-ui, -apple-system, "Segoe UI", sans-serif;
  font-size: 16px;
  line-height: 1.55;
}

a {
  color: var(--dc-link);
  text-decoration-thickness: 0.08em;
  text-underline-offset: 0.18em;
}

h1,
h2,
h3 {
  font-family: "Roboto Flex", "Roboto", system-ui, sans-serif;
  font-weight: 800;
  letter-spacing: -0.02em;
  line-height: 1.1;
  margin: 0;
}

h1 {
  font-size: clamp(2.4rem, 4vw + 1rem, 3.5rem);
  letter-spacing: -0.025em;
}

h2 {
  font-size: 1.4rem;
  font-weight: 700;
  letter-spacing: -0.015em;
}

h3 {
  font-size: 1.2rem;
  font-weight: 700;
}

.eyebrow {
  font-family: "Roboto Mono", ui-monospace, monospace;
  font-size: 0.78rem;
  font-weight: 500;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--dc-muted);
  margin: 0 0 6px;
}

.site-header,
.site-footer {
  background: var(--dc-ink);
  color: #fff;
}

.site-header a,
.site-footer a {
  color: #fff;
  text-decoration: none;
}

.site-header {
  border-bottom: 1px solid #000;
}

.site-nav,
.site-footer-inner,
main {
  width: var(--dc-container);
  margin: 0 auto;
}

.site-nav {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  min-height: 64px;
}

.brand {
  display: inline-flex;
  align-items: center;
  gap: 12px;
  color: #fff;
  font-weight: 700;
  text-decoration: none;
}

.brand-mark {
  width: 36px;
  height: 36px;
  border-radius: var(--dc-radius);
  display: block;
  object-fit: cover;
}

.brand-name {
  font-size: 1rem;
}

.nav-links {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 14px 22px;
  font-size: 0.92rem;
  font-weight: 600;
}

.show-hero {
  display: grid;
  grid-template-columns: minmax(0, 1.4fr) minmax(180px, 280px);
  gap: 40px;
  align-items: center;
  padding: 56px 0 36px;
}

.show-hero h1 {
  margin: 4px 0 12px;
}

.show-tagline {
  max-width: 60ch;
  color: var(--dc-muted);
  font-size: 1.1rem;
  margin: 0 0 20px;
}

.show-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.show-artwork {
  width: 100%;
  max-width: 280px;
  justify-self: end;
  border-radius: var(--dc-radius);
  box-shadow: 0 18px 36px rgb(0 0 0 / 0.10);
}

.button-primary,
.button-secondary {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 42px;
  padding: 0 18px;
  border-radius: 999px;
  font-weight: 600;
  text-decoration: none;
}

.button-primary {
  background: var(--dc-ink);
  color: #fff;
  border: 1px solid var(--dc-ink);
}

.button-secondary {
  background: var(--dc-paper);
  color: var(--dc-ink);
  border: 1px solid var(--dc-ink);
}

.link-band {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px 18px;
  margin: 0 0 32px;
  padding: 16px 0;
  border-top: 1px solid var(--dc-line);
  border-bottom: 1px solid var(--dc-line);
  font-size: 0.92rem;
  font-weight: 600;
}

.link-band a {
  color: var(--dc-ink);
  text-decoration: none;
}

.filter-form {
  display: grid;
  grid-template-columns: minmax(0, 2fr) minmax(0, 1.6fr) minmax(0, 1fr) minmax(0, 1fr) auto;
  gap: 12px;
  margin: 0 0 28px;
  padding: 14px;
  border: 1px solid var(--dc-line);
  border-radius: var(--dc-radius);
}

.filter-form input,
.filter-form select {
  width: 100%;
  min-height: 40px;
  padding: 0 12px;
  border: 1px solid var(--dc-line);
  border-radius: var(--dc-radius);
  background: var(--dc-paper);
  font: inherit;
}

.filter-date {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}

.filter-date input,
.filter-date input[type="date"] {
  flex: 1;
  min-width: 0;
}

.visually-hidden {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

.filter-form button {
  min-height: 40px;
  padding: 0 18px;
  background: var(--dc-ink);
  color: #fff;
  border: 0;
  border-radius: 999px;
  font-weight: 600;
  cursor: pointer;
}

.episode-list {
  display: grid;
  gap: 0;
  padding: 0 0 56px;
}

.episode-row {
  display: grid;
  grid-template-columns: 36px 1fr;
  gap: 16px;
  padding: 22px 0;
  border-top: 1px solid var(--dc-line);
  text-decoration: none;
  color: inherit;
}

.episode-row:first-child {
  border-top: 0;
}

.episode-row:hover {
  background: rgb(13 13 13 / 0.03);
}

.play-circle {
  width: 36px;
  height: 36px;
  border: 1.5px solid var(--dc-ink);
  border-radius: 999px;
  display: grid;
  place-items: center;
  align-self: start;
  margin-top: 4px;
}

.play-circle svg {
  width: 14px;
  height: 14px;
  fill: var(--dc-ink);
}

.episode-row h2 {
  margin: 2px 0 6px;
}

.episode-summary {
  color: var(--dc-muted);
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  overflow: hidden;
  margin: 0;
}

.no-results {
  padding: 48px 0;
  text-align: center;
  color: var(--dc-muted);
}

.episode-detail {
  padding: 36px 0 64px;
}

.back-link {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--dc-muted);
  text-decoration: none;
  margin-bottom: 20px;
}

.episode-hero {
  display: grid;
  grid-template-columns: minmax(180px, 280px) minmax(0, 1fr);
  gap: 40px;
  align-items: start;
  margin-bottom: 28px;
}

.episode-hero .show-artwork {
  justify-self: start;
}

.episode-hero h1 {
  margin: 4px 0 14px;
  font-size: clamp(1.8rem, 2.5vw + 1rem, 2.4rem);
  letter-spacing: -0.02em;
}

.episode-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 18px;
  font-family: "Roboto Mono", ui-monospace, monospace;
  font-size: 0.78rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--dc-muted);
}

.episode-actions a {
  color: inherit;
  text-decoration: none;
}

.audio-panel {
  margin: 28px 0;
}

.audio-panel p {
  margin: 0;
  color: var(--dc-muted);
  font-weight: 600;
}

.show-notes {
  max-width: 720px;
  font-size: 1.02rem;
}

.show-notes h2,
.show-notes h3 {
  font-family: "Roboto", system-ui, sans-serif;
  font-weight: 700;
  letter-spacing: 0;
}

.show-notes h2 {
  font-size: 1.15rem;
  margin: 28px 0 8px;
}

.show-notes h3 {
  font-size: 1rem;
  margin: 22px 0 6px;
}

.show-notes a {
  color: var(--dc-link);
}

.pagination-nav {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 14px;
  padding: 24px 0 56px;
  font-weight: 600;
}

.pagination-nav a {
  display: inline-flex;
  align-items: center;
  min-height: 40px;
  padding: 0 16px;
  border: 1px solid var(--dc-line);
  border-radius: 999px;
  color: var(--dc-ink);
  text-decoration: none;
}

.site-footer-inner {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  gap: 16px;
  padding: 24px 0;
  font-size: 0.9rem;
}

.site-footer .social-links {
  display: flex;
  gap: 16px;
}

.status-page {
  padding: 80px 0;
  text-align: center;
}

.status-page h1 {
  margin-bottom: 12px;
}

.status-page p {
  color: var(--dc-muted);
}

@media (max-width: 760px) {
  .site-nav,
  .show-hero,
  .episode-hero,
  .filter-form {
    grid-template-columns: 1fr;
    align-items: flex-start;
  }

  .show-hero {
    padding-top: 36px;
  }

  .show-artwork {
    justify-self: start;
    max-width: 220px;
  }

  .episode-hero .show-artwork {
    max-width: 200px;
  }
}
```

- [ ] **Step 2: Verify the file is saved correctly**

Run: `wc -l django_chat/static/django_chat/css/site.css`
Expected: roughly 350 lines.

- [ ] **Step 3: Stage and request commit approval**
```bash
git add django_chat/static/django_chat/css/site.css
git status --short
# Suggested commit message (commit only when the user explicitly approves):
#   "Replace site.css with djangochat.com-aligned tokens"
```

---

## Task 2: Self-host Roboto fonts

**Files:**
- Create: `django_chat/static/fonts/Roboto-Variable.woff2`
- Create: `django_chat/static/fonts/RobotoFlex-Variable.woff2`
- Create: `django_chat/static/fonts/RobotoMono-Variable.woff2`
- Modify: `django_chat/static/django_chat/css/site.css` (prepend `@font-face`)

- [ ] **Step 1: Create the fonts directory**

Run: `mkdir -p django_chat/static/fonts`

- [ ] **Step 2: Download the three variable fonts**

Run:

```bash
curl -L -o django_chat/static/fonts/Roboto-Variable.woff2 \
  'https://fonts.gstatic.com/s/roboto/v48/KFO7CnqEu92Fr1ME7kSn66aGLdTylUAMQXC89YmC2DPNWubEbWmRwm5qb1Yj.woff2'
curl -L -o django_chat/static/fonts/RobotoFlex-Variable.woff2 \
  'https://fonts.gstatic.com/s/robotoflex/v34/NaNeepOXO_NexZs0b5QrzlOHb8wCikXpYqmZsWI-__OGQg.woff2'
curl -L -o django_chat/static/fonts/RobotoMono-Variable.woff2 \
  'https://fonts.gstatic.com/s/robotomono/v23/L0xuDF4xlVMF-BfR8bXMIhJHg45mwgGEFl0_3vqPPRNb_g.woff2'
ls -lh django_chat/static/fonts/
```

Expected: three `.woff2` files between 100 KB and 800 KB each.

If any download yields HTML (Google sometimes redirects), copy the matching `woff2` URL by visiting `https://fonts.googleapis.com/css2?family=Roboto&family=Roboto+Flex&family=Roboto+Mono&display=swap` in a browser, picking the unicode-range `latin` variant for each, and re-running curl with the new URL. The exact filename suffix is not load-bearing.

- [ ] **Step 3: Add `@font-face` rules to the top of `site.css`**

Insert these blocks at the very top of `django_chat/static/django_chat/css/site.css`, before the existing `:root` block:

```css
@font-face {
  font-family: "Roboto";
  src: url("/static/fonts/Roboto-Variable.woff2") format("woff2-variations"),
       url("/static/fonts/Roboto-Variable.woff2") format("woff2");
  font-weight: 100 900;
  font-style: normal;
  font-display: swap;
}

@font-face {
  font-family: "Roboto Flex";
  src: url("/static/fonts/RobotoFlex-Variable.woff2") format("woff2-variations"),
       url("/static/fonts/RobotoFlex-Variable.woff2") format("woff2");
  font-weight: 100 1000;
  font-style: normal;
  font-display: swap;
}

@font-face {
  font-family: "Roboto Mono";
  src: url("/static/fonts/RobotoMono-Variable.woff2") format("woff2-variations"),
       url("/static/fonts/RobotoMono-Variable.woff2") format("woff2");
  font-weight: 100 700;
  font-style: normal;
  font-display: swap;
}
```

- [ ] **Step 4: Verify the dev server picks up the static files**

Run: `just runserver` in one terminal, then in another: `curl -sI http://127.0.0.1:8000/static/fonts/Roboto-Variable.woff2 | head -1`. Stop the dev server.
Expected: `HTTP/1.1 200 OK`.

- [ ] **Step 5: Stage and request commit approval**
```bash
git add django_chat/static/fonts django_chat/static/django_chat/css/site.css
git status --short
# Suggested commit message (commit only when the user explicitly approves):
#   "Self-host Roboto, Roboto Flex, Roboto Mono variable fonts"
```

---

## Task 3: Generate favicon and OG image assets

**Files:**
- Create: `django_chat/static/django_chat/favicon.ico`
- Create: `django_chat/static/django_chat/favicon.svg`
- Create: `django_chat/static/django_chat/apple-touch-icon.png`
- Create: `django_chat/static/django_chat/og-image.png`

- [ ] **Step 1: Download the show artwork**

The show artwork URL is stable in the captured fixtures
(`django_chat/imports/tests/fixtures/django_chat_source/simplecast_podcast.json`).
Use it directly:

```bash
curl -L -o /tmp/dc-source.jpg \
  'https://image.simplecastcdn.com/images/19d48b52-7d9d-4294-8dbf-7f2739ba2e91/259ee18c-8fe2-4e10-8ef7-b95987f5fb24/1549072581-artwork.jpg'
file /tmp/dc-source.jpg
```

Expected: `JPEG image data, ...`. If the URL has rotted upstream, re-fetch
the current value from the running site:

```bash
just manage shell -c "from django_chat.imports.models import PodcastSourceMetadata; print(PodcastSourceMetadata.objects.first().image_url)"
```

(requires `just manage import_django_chat_sample` first). Re-run the curl
with the printed URL.

- [ ] **Step 2: Generate icon files via Pillow**

Pillow is a transitive dep of Wagtail, so it's already installed. Run:

```bash
uv run python - <<'PY'
from pathlib import Path
from PIL import Image

src = Image.open("/tmp/dc-source.jpg").convert("RGB")
out_dir = Path("django_chat/static/django_chat")
out_dir.mkdir(parents=True, exist_ok=True)

apple = src.resize((180, 180), Image.LANCZOS)
apple.save(out_dir / "apple-touch-icon.png", "PNG")

og = src.resize((1200, 1200), Image.LANCZOS)
og.save(out_dir / "og-image.png", "PNG")

ico_sizes = [(16, 16), (32, 32), (48, 48)]
src.save(
    out_dir / "favicon.ico",
    format="ICO",
    sizes=ico_sizes,
)

print("wrote:", *(p.name for p in out_dir.glob("favicon*") for _ in [None]))
print("wrote:", *(p.name for p in out_dir.glob("apple-touch-icon*") for _ in [None]))
print("wrote:", *(p.name for p in out_dir.glob("og-image*") for _ in [None]))
PY
ls -lh django_chat/static/django_chat/favicon.ico django_chat/static/django_chat/apple-touch-icon.png django_chat/static/django_chat/og-image.png
```

Expected: three new files, sizes roughly 5 KB / 30 KB / 250 KB.

- [ ] **Step 3: Generate `favicon.svg` (single-file scalable favicon)**

Write the file at `django_chat/static/django_chat/favicon.svg` with this content (Django Chat green chat-bubble mark — recognisable at 16px):

```xml
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <rect width="64" height="64" rx="10" fill="#44b78b"/>
  <path d="M14 20a6 6 0 0 1 6-6h24a6 6 0 0 1 6 6v18a6 6 0 0 1-6 6H28l-10 8v-8h-4a6 6 0 0 1-6-6Z" fill="#ffffff"/>
  <text x="32" y="35" text-anchor="middle" font-family="Roboto, sans-serif" font-weight="800" font-size="13" fill="#0d0d0d">DC</text>
</svg>
```

- [ ] **Step 4: Stage and request commit approval**
```bash
git add django_chat/static/django_chat/favicon.ico \
        django_chat/static/django_chat/favicon.svg \
        django_chat/static/django_chat/apple-touch-icon.png \
        django_chat/static/django_chat/og-image.png
git status --short
# Suggested commit message (commit only when the user explicitly approves):
#   "Add Django Chat favicon and OG image assets"
```

---

## Task 4: Update `base.html` shell

**Files:**
- Modify: `django_chat/templates/cast/django_chat/base.html`
- Create: `django_chat/templates/cast/django_chat/_meta.html`

- [ ] **Step 1: Create the OG/Twitter defaults partial**

Write `django_chat/templates/cast/django_chat/_meta.html`:

```django
{% load static %}
{% firstof podcast blog as show %}
{% firstof page.seo_title page.title "Django Chat" as resolved_title %}
{% firstof page.search_description show.description "" as resolved_description %}
{% firstof source_metadata.image_url "" as resolved_image %}
<meta property="og:site_name" content="Django Chat">
<meta property="og:title" content="{{ resolved_title }}">
<meta property="og:description" content="{{ resolved_description|striptags }}">
{% if resolved_image %}<meta property="og:image" content="{{ resolved_image }}">{% else %}<meta property="og:image" content="{{ request.scheme }}://{{ request.get_host }}{% static 'django_chat/og-image.png' %}">{% endif %}
{% if resolved_canonical_url %}<meta property="og:url" content="{{ resolved_canonical_url }}">{% endif %}
<meta property="og:type" content="{{ og_type|default:'website' }}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{{ resolved_title }}">
<meta name="twitter:description" content="{{ resolved_description|striptags }}">
{% if resolved_image %}<meta name="twitter:image" content="{{ resolved_image }}">{% else %}<meta name="twitter:image" content="{{ request.scheme }}://{{ request.get_host }}{% static 'django_chat/og-image.png' %}">{% endif %}
```

- [ ] **Step 2: Rewrite `base.html`**

Replace `django_chat/templates/cast/django_chat/base.html` with:

```django
{% load static %}
{% firstof podcast blog as show %}
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta http-equiv="X-UA-Compatible" content="IE=edge">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="description" content="{{ page.search_description }}">
    <title>{% block title %}{% if page.seo_title %}{{ page.seo_title }}{% else %}{{ page.title }}{% endif %}{% endblock title %} | Django Chat</title>
    {% firstof canonical_url absolute_page_url page_url as resolved_canonical_url %}
    {% if resolved_canonical_url %}<link rel="canonical" href="{{ resolved_canonical_url }}">{% endif %}
    <link rel="icon" type="image/svg+xml" href="{% static 'django_chat/favicon.svg' %}">
    <link rel="alternate icon" type="image/x-icon" href="{% static 'django_chat/favicon.ico' %}">
    <link rel="apple-touch-icon" sizes="180x180" href="{% static 'django_chat/apple-touch-icon.png' %}">
    <link rel="stylesheet" href="{% static 'cast_bootstrap5/css/bootstrap5/bootstrap.min.css' %}">
    <link rel="stylesheet" href="{% static 'django_chat/css/site.css' %}">
    {% block meta %}
      {% include "./_meta.html" %}
    {% endblock meta %}
    {# episode.html overrides the meta block above to pass og_type="article" #}
  </head>
  <body>
    <header class="site-header">
      <nav class="site-nav" aria-label="Primary">
        <a class="brand" href="/episodes/" aria-label="Django Chat">
          {% if source_metadata.image_url %}
            <img class="brand-mark" src="{{ source_metadata.image_url }}" alt="">
          {% else %}
            <img class="brand-mark" src="{% static 'django_chat/apple-touch-icon.png' %}" alt="">
          {% endif %}
          <span class="brand-name">Django Chat</span>
        </a>
        <div class="nav-links">
          <a href="/episodes/">Episodes</a>
          {% if source_metadata %}
            {% for link in source_metadata.visible_menu_links %}
              <a href="{{ link.url }}"{% if link.new_window %} target="_blank" rel="noopener noreferrer"{% endif %}>{{ link.name }}</a>
            {% endfor %}
          {% endif %}
        </div>
      </nav>
    </header>

    {% block content %}{% endblock content %}

    <footer class="site-footer">
      <div class="site-footer-inner">
        <div>
          <strong>Django Chat</strong>
          {% if show.subtitle %}<div>{{ show.subtitle }}</div>{% endif %}
        </div>
        {% if source_metadata %}
          <nav class="social-links" aria-label="Social links">
            {% for link in source_metadata.visible_social_links %}
              <a href="{{ link.url }}"{% if link.new_window %} target="_blank" rel="noopener noreferrer"{% endif %}>{{ link.name }}</a>
            {% endfor %}
          </nav>
        {% endif %}
        <div>
          Powered by <a href="https://github.com/ephes/django-cast">django-cast</a>
        </div>
      </div>
    </footer>
    {% block javascript %}
      <script defer src="{% static 'cast_bootstrap5/js/bootstrap5/bootstrap.bundle.min.js' %}"></script>
    {% endblock javascript %}
  </body>
</html>
```

- [ ] **Step 3: Smoke-test the page renders**

Run: `just test django_chat/imports/tests/test_sample_site_routes.py::test_imported_sample_index_renders_django_chat_theme_and_source_links -x`
Expected: PASS (the test only checks for content strings — those still appear in the new layout). If it fails because the test asserts a string we removed (e.g. the eyebrow `Django Web Framework Podcast`), defer the failure to Task 11; the bulk of the assertions should still pass.

- [ ] **Step 4: Stage and request commit approval**
```bash
git add django_chat/templates/cast/django_chat/base.html \
        django_chat/templates/cast/django_chat/_meta.html
git status --short
# Suggested commit message (commit only when the user explicitly approves):
#   "Brand site shell with show artwork mark, OG metadata, favicon"
```

---

## Task 5: Configure CAST_FILTERSET_FACETS

**Files:**
- Modify: `config/settings/base.py`

- [ ] **Step 1: Add the setting**

In `config/settings/base.py`, find the section near the bottom that defines `DJANGO_VITE` (around line 241). Immediately after the closing `}` of `DJANGO_VITE`, add:

```python
CAST_FILTERSET_FACETS = ["search", "date", "date_facets", "o"]
```

- [ ] **Step 2: Verify the setting loads**

Run: `just manage shell -c "from cast import appsettings; print(appsettings.CAST_FILTERSET_FACETS)"`
Expected: `['search', 'date', 'date_facets', 'o']`.

- [ ] **Step 3: Stage and request commit approval**
```bash
git add config/settings/base.py
git status --short
# Suggested commit message (commit only when the user explicitly approves):
#   "Restrict CAST_FILTERSET_FACETS to search, date, and ordering"
```

---

## Task 6: Extend `podcast_episode_index` view (TDD)

**Files:**
- Modify: `django_chat/core/views.py`
- Create: `django_chat/core/tests/test_episode_index_filter.py`

- [ ] **Step 1: Write a filtering test that fails**

Create `django_chat/core/tests/test_episode_index_filter.py`:

```python
from __future__ import annotations

import pytest
from django.test import Client

from django_chat.imports.import_sample import import_django_chat_sample


@pytest.mark.django_db
def test_episode_index_filters_by_search_query(client: Client) -> None:
    import_django_chat_sample()

    response = client.get("/episodes/?search=tasks")

    assert response.status_code == 200
    body = response.content.decode()
    assert "Django Tasks - Jake Howard" in body
    assert "How to Learn Django" not in body


@pytest.mark.django_db
def test_episode_index_unfiltered_lists_all_sample_episodes(client: Client) -> None:
    import_django_chat_sample()

    response = client.get("/episodes/")

    assert response.status_code == 200
    body = response.content.decode()
    assert "Django Tasks - Jake Howard" in body
    assert "How to Learn Django" in body


@pytest.mark.django_db
def test_episode_index_exposes_filterset_form_fields(client: Client) -> None:
    import_django_chat_sample()

    response = client.get("/episodes/")

    body = response.content.decode()
    assert 'name="search"' in body
    assert 'name="date_after"' in body
    assert 'name="date_before"' in body
    assert 'name="date_facets"' in body
    assert 'name="o"' in body


@pytest.mark.django_db
def test_episode_index_no_results_state_renders_when_search_misses(
    client: Client,
) -> None:
    import_django_chat_sample()

    response = client.get("/episodes/?search=zzzzzznotaword")

    assert response.status_code == 200
    body = response.content.decode()
    assert "No episodes match your filters." in body
```

- [ ] **Step 2: Run the new tests; expect failure**

Run: `just test django_chat/core/tests/test_episode_index_filter.py -x`
Expected: assertions fail (filterset not yet wired, no-results message not yet emitted).

- [ ] **Step 3: Rewrite the view to wire `PostFilterset` and pagination**

Replace `django_chat/core/views.py` with:

```python
from __future__ import annotations

from typing import Any, cast as type_cast

from cast.filters import PostFilterset
from cast.models import Episode, Podcast
from django.core.paginator import Paginator
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render

from django_chat.imports.models import PodcastSourceMetadata

EPISODES_PER_PAGE = 20


def podcast_episode_index(request: HttpRequest) -> HttpResponse:
    podcast = get_object_or_404(Podcast.objects.live(), slug="episodes")

    base_qs = (
        Episode.objects.live().child_of(podcast).order_by("-visible_date")
    )
    filterset = PostFilterset(data=request.GET, queryset=base_qs)
    filtered_qs = filterset.qs

    paginator = Paginator(filtered_qs, EPISODES_PER_PAGE)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    posts = list(page_obj.object_list)
    for post in posts:
        type_cast(Any, post).page_url = post.get_url(request=request)

    parameters = request.GET.copy()
    parameters.pop("page", None)
    parameters_querystring = parameters.urlencode()
    if parameters_querystring:
        parameters_suffix = "&" + parameters_querystring
    else:
        parameters_suffix = ""

    template_base_dir = podcast.get_template_base_dir(type_cast(Any, request))
    type_cast(Any, request).cast_site_template_base_dir = template_base_dir
    canonical_url = request.build_absolute_uri(
        podcast.get_url(request=request) or request.path
    )
    source_metadata = (
        PodcastSourceMetadata.objects.filter(podcast=podcast)
        .prefetch_related("source_links")
        .first()
    )

    return render(
        request,
        "cast/django_chat/blog_list_of_posts.html",
        {
            "page": podcast,
            "blog": podcast,
            "podcast": podcast,
            "posts": posts,
            "object_list": posts,
            "page_obj": page_obj,
            "paginator": paginator,
            "is_paginated": page_obj.has_other_pages(),
            "page_number": page_obj.number,
            "has_previous": page_obj.has_previous(),
            "previous_page_number": page_obj.previous_page_number() if page_obj.has_previous() else None,
            "has_next": page_obj.has_next(),
            "next_page_number": page_obj.next_page_number() if page_obj.has_next() else None,
            "parameters": parameters_suffix,
            "filterset": filterset,
            "canonical_url": canonical_url,
            "source_metadata": source_metadata,
            "template_base_dir": template_base_dir,
        },
    )
```

- [ ] **Step 4: Add the no-results block to `blog_list_of_posts.html` so the test sees the string**

Open `django_chat/templates/cast/django_chat/blog_list_of_posts.html`. Inside the `{% block content %}` body, just before the existing `<section class="episode-list">`, insert:

```django
{% if not posts %}
  <p class="no-results">No episodes match your filters. <a href="{% url 'django_chat_episode_index' %}">Clear filters</a>.</p>
{% endif %}
```

(The full template gets rewritten in Task 8; this targeted insert is enough to flip the test green now and is overwritten cleanly later.)

- [ ] **Step 5: Re-render the filter form fields so the assertion test passes**

Still in `blog_list_of_posts.html`, add this just below the distribution `link-band` section (or just before the `episode-list` section if no `link-band` is present in the current template):

```django
{% if filterset %}
  {% include "./_filter_form.html" with form=filterset.form %}
{% endif %}
```

- [ ] **Step 6: Stub the filter form partial**

Create `django_chat/templates/cast/django_chat/_filter_form.html`:

```django
<form method="get" class="filter-form" aria-label="Filter episodes">
  <label class="visually-hidden" for="id_search">Search</label>
  <input id="id_search" type="text" name="search" placeholder="Search episodes" value="{{ form.search.value|default_if_none:'' }}">

  <div class="filter-date">
    <label class="visually-hidden">Date range</label>
    {# DateFromToRangeFilter renders two <input type="date"> with names date_after and date_before #}
    {{ form.date }}
  </div>

  <select name="date_facets" aria-label="Date facets">
    <option value="">All dates</option>
    {% for value, label in form.date_facets.field.choices %}
      <option value="{{ value }}"{% if form.date_facets.value == value %} selected{% endif %}>{{ label }}</option>
    {% endfor %}
  </select>

  <select name="o" aria-label="Sort order">
    <option value="">Newest first</option>
    {% for value, label in form.o.field.choices %}
      {% if value %}<option value="{{ value }}"{% if form.o.value == value %} selected{% endif %}>{{ label }}</option>{% endif %}
    {% endfor %}
  </select>

  <button type="submit">Filter</button>
</form>
```

The visually-hidden label class can be added to `site.css` if needed; if Django renders `{{ form.date }}` with surrounding markup that conflicts with the grid, fall back to two explicit `<input type="date" name="date_after">` / `<input type="date" name="date_before">` elements (matching what `DateFromToRangeFilter` accepts).

- [ ] **Step 7: Re-run the filter tests**

Run: `just test django_chat/core/tests/test_episode_index_filter.py -x`
Expected: all four tests PASS.

- [ ] **Step 8: Stage and request commit approval**
```bash
git add django_chat/core/views.py \
        django_chat/core/tests/test_episode_index_filter.py \
        django_chat/templates/cast/django_chat/blog_list_of_posts.html \
        django_chat/templates/cast/django_chat/_filter_form.html
git status --short
# Suggested commit message (commit only when the user explicitly approves):
#   "Wire PostFilterset and pagination in podcast_episode_index"
```

---

## Task 7: Pagination test with forced small page size

**Files:**
- Create: `django_chat/core/tests/test_episode_pagination.py`

- [ ] **Step 1: Write the pagination test**

Create `django_chat/core/tests/test_episode_pagination.py`:

```python
from __future__ import annotations

from unittest.mock import patch

import pytest
from django.test import Client

from django_chat.imports.import_sample import import_django_chat_sample


@pytest.mark.django_db
def test_pagination_markup_hidden_for_eight_episode_fixture(client: Client) -> None:
    import_django_chat_sample()

    response = client.get("/episodes/")

    body = response.content.decode()
    assert response.context["is_paginated"] is False
    assert 'class="pagination-nav"' not in body


@pytest.mark.django_db
def test_pagination_markup_visible_when_page_size_is_small(client: Client) -> None:
    import_django_chat_sample()

    with patch("django_chat.core.views.EPISODES_PER_PAGE", 3):
        response = client.get("/episodes/?search=django")

    body = response.content.decode()
    assert response.context["is_paginated"] is True
    assert 'class="pagination-nav"' in body
    # parameters context preserves the active filter on Older/Newer links
    assert "search=django" in body


@pytest.mark.django_db
def test_pagination_parameters_context_value_strips_page_only(client: Client) -> None:
    import_django_chat_sample()

    with patch("django_chat.core.views.EPISODES_PER_PAGE", 3):
        response = client.get("/episodes/?search=django&page=2")

    parameters = response.context["parameters"]
    assert "search=django" in parameters
    assert "page=" not in parameters
```

- [ ] **Step 2: Run the pagination tests**

Run: `just test django_chat/core/tests/test_episode_pagination.py -x`
Expected: PASS (the view already wires `is_paginated`, `parameters`, etc.). If the third test fails, double-check the view's `parameters_suffix` computation in Task 6; it must omit `page=` and prepend `&` only when there is content.

- [ ] **Step 3: Stage and request commit approval**
```bash
git add django_chat/core/tests/test_episode_pagination.py
git status --short
# Suggested commit message (commit only when the user explicitly approves):
#   "Cover pagination contract with forced-small-page-size tests"
```

---

## Task 7b: Add `duration_minutes` template filter

**Files:**
- Create: `django_chat/core/templatetags/__init__.py`
- Create: `django_chat/core/templatetags/dc_filters.py`
- Create: `django_chat/core/tests/test_dc_filters.py`

- [ ] **Step 1: Create the templatetags package**

Run: `mkdir -p django_chat/core/templatetags && touch django_chat/core/templatetags/__init__.py`

- [ ] **Step 2: Write the failing tests first**

Create `django_chat/core/tests/test_dc_filters.py`:

```python
from __future__ import annotations

import pytest

from django_chat.core.templatetags.dc_filters import duration_minutes


@pytest.mark.parametrize(
    "seconds,expected",
    [
        (4663, "78 MIN"),
        (60, "1 MIN"),
        (29, "0 MIN"),
        (None, ""),
        (0, ""),
    ],
)
def test_duration_minutes_formats_or_returns_empty(seconds, expected):
    assert duration_minutes(seconds) == expected
```

- [ ] **Step 3: Run the tests; expect ImportError**

Run: `just test django_chat/core/tests/test_dc_filters.py -x`
Expected: FAIL — module not yet defined.

- [ ] **Step 4: Implement the filter**

Create `django_chat/core/templatetags/dc_filters.py`:

```python
from __future__ import annotations

from django import template

register = template.Library()


@register.filter
def duration_minutes(seconds: int | None) -> str:
    """Render a duration in seconds as a `'N MIN'` label, or empty string."""
    if not seconds:
        return ""
    minutes = round(int(seconds) / 60)
    return f"{minutes} MIN"
```

- [ ] **Step 5: Re-run the tests**

Run: `just test django_chat/core/tests/test_dc_filters.py -x`
Expected: all parametrised cases PASS.

- [ ] **Step 6: Stage**

```bash
git add django_chat/core/templatetags/__init__.py \
        django_chat/core/templatetags/dc_filters.py \
        django_chat/core/tests/test_dc_filters.py
git status --short
```

Suggested commit message (commit only if explicitly approved):
`Add duration_minutes template filter`

---

## Task 8: Restyle `blog_list_of_posts.html`

**Files:**
- Modify: `django_chat/templates/cast/django_chat/blog_list_of_posts.html`

- [ ] **Step 1: Rewrite the whole template**

Replace `django_chat/templates/cast/django_chat/blog_list_of_posts.html` with:

```django
{% extends "./base.html" %}
{% load wagtailcore_tags %}
{% load dc_filters %}

{% block title %}{{ page.title }}{% endblock title %}

{% block content %}
  {% firstof podcast blog as show %}
  <main>
    <section class="show-hero">
      <div class="show-copy">
        <p class="eyebrow">A biweekly podcast on the Django Web Framework</p>
        <h1>{{ page.title }}</h1>
        {% if page.description %}
          <div class="show-tagline">{{ page.description|richtext }}</div>
        {% endif %}
        <div class="show-actions" aria-label="Subscribe">
          {% for link in source_metadata.visible_distribution_links %}
            {% if link.name == "Apple Podcasts" %}
              <a class="button-secondary" href="{{ link.url }}" target="_blank" rel="noopener noreferrer">Apple Podcasts</a>
            {% endif %}
          {% endfor %}
          {% if source_metadata.website_url %}
            <a class="button-primary" href="{{ source_metadata.website_url }}" target="_blank" rel="noopener noreferrer">Listen &amp; Subscribe</a>
          {% else %}
            <a class="button-primary" href="{% url 'cast:podcast_feed_rss' slug=podcast.slug audio_format='mp3' %}">Listen &amp; Subscribe</a>
          {% endif %}
        </div>
      </div>
      {% if source_metadata.image_url %}
        <img class="show-artwork" src="{{ source_metadata.image_url }}" alt="Django Chat artwork">
      {% endif %}
    </section>

    {% if source_metadata %}
      <section class="link-band" aria-label="Listen on">
        {% for link in source_metadata.visible_distribution_links %}
          <a href="{{ link.url }}" target="_blank" rel="noopener noreferrer">{{ link.name }}</a>
        {% endfor %}
      </section>
    {% endif %}

    {% if filterset %}
      {% include "./_filter_form.html" with form=filterset.form %}
    {% endif %}

    {% if not posts %}
      <p class="no-results">No episodes match your filters. <a href="{% url 'django_chat_episode_index' %}">Clear filters</a>.</p>
    {% else %}
      <section class="episode-list" aria-label="Episodes">
        {% for post in posts %}
          <a class="episode-row" href="{{ post.page_url }}">
            <span class="play-circle" aria-hidden="true">
              <svg viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>
            </span>
            <div>
              <p class="eyebrow">
                <time datetime="{{ post.visible_date|date:'c' }}">{{ post.visible_date|date:'M j, Y' }}</time>
                {% with episode_number=post.django_chat_source_metadata.episode_number duration=post.django_chat_source_metadata.duration_seconds %}
                  {% if episode_number %} · E{{ episode_number }}{% endif %}
                  {% with duration_label=duration|duration_minutes %}{% if duration_label %} · {{ duration_label }}{% endif %}{% endwith %}
                {% endwith %}
              </p>
              <h2>{{ post.title }}</h2>
              {% for block in post.body %}
                {% if block.block_type != "detail" %}
                  <p class="episode-summary">
                    {% for child_block in block.value %}
                      {% if child_block.block_type == "paragraph" %}{{ child_block|striptags|truncatewords:32 }}{% endif %}
                    {% endfor %}
                  </p>
                {% endif %}
              {% endfor %}
            </div>
          </a>
        {% endfor %}
      </section>
    {% endif %}

    {% if is_paginated %}
      {% include "./pagination.html" %}
    {% endif %}
  </main>
{% endblock content %}
```

- [ ] **Step 2: Run all view-level tests**

Run: `just test django_chat/core/tests/ django_chat/imports/tests/test_sample_site_routes.py -x`
Expected: any failures point at strings the old template emitted that are no longer there. Capture them — we'll address them in Task 11. Filtering and pagination tests must still pass.

- [ ] **Step 3: Stage and request commit approval**
```bash
git add django_chat/templates/cast/django_chat/blog_list_of_posts.html
git status --short
# Suggested commit message (commit only when the user explicitly approves):
#   "Restyle episode list with single-column rows and filter form"
```

---

## Task 9: Restyle `pagination.html`

**Files:**
- Modify: `django_chat/templates/cast/django_chat/pagination.html`

- [ ] **Step 1: Replace the file**

The interface stays the same; only the markup wrapper picks up the `pagination-nav` class which `site.css` already styles.

```django
<nav class="pagination-nav" aria-label="Episode pages">
  {% if has_previous %}
    <a href="?page={{ previous_page_number }}{{ parameters }}">← Newer</a>
  {% endif %}
  <span>Page {{ page_number }}</span>
  {% if has_next %}
    <a href="?page={{ next_page_number }}{{ parameters }}">Older →</a>
  {% endif %}
</nav>
```

- [ ] **Step 2: Re-run the pagination tests**

Run: `just test django_chat/core/tests/test_episode_pagination.py -x`
Expected: PASS.

- [ ] **Step 3: Stage and request commit approval**
```bash
git add django_chat/templates/cast/django_chat/pagination.html
git status --short
# Suggested commit message (commit only when the user explicitly approves):
#   "Refresh pagination markup wrapper"
```

---

## Task 10: Restyle `episode.html` and wire Podlove

**Files:**
- Modify: `django_chat/templates/cast/django_chat/episode.html`

- [ ] **Step 1: Replace the template**

```django
{% extends "./base.html" %}
{% load wagtailcore_tags %}
{% load django_vite %}
{% load dc_filters %}

{% block title %}{{ page.title }}{% endblock title %}

{% block meta %}
  {% include "./_meta.html" with og_type="article" %}
{% endblock meta %}

{% block content %}
  <main>
    <article class="episode-detail">
      <a class="back-link" href="{% url 'django_chat_episode_index' %}">← Back to Episodes</a>

      <header class="episode-hero">
        {% if source_metadata.image_url %}
          <img class="show-artwork" src="{{ source_metadata.image_url }}" alt="">
        {% endif %}
        <div>
          <p class="eyebrow">
            <time datetime="{{ page.visible_date|date:'c' }}">{{ page.visible_date|date:'F j, Y' }}</time>
            {% with episode_number=page.django_chat_source_metadata.episode_number duration=page.django_chat_source_metadata.duration_seconds %}
              {% if episode_number %} · E{{ episode_number }}{% endif %}
              {% with duration_label=duration|duration_minutes %}{% if duration_label %} · {{ duration_label }}{% endif %}{% endwith %}
            {% endwith %}
          </p>
          <h1>{{ page.title }}</h1>
          <div class="episode-actions">
            {% if episode.podcast_audio and episode.podcast_audio.mp3 %}
              <a href="{{ episode.podcast_audio.mp3.url }}" download>Download MP3</a>
            {% endif %}
            {% if episode_transcript_url %}
              <a href="{{ episode_transcript_url }}">Transcript</a>
            {% endif %}
            <a href="https://twitter.com/intent/tweet?url={{ resolved_canonical_url|urlencode }}&text={{ page.title|urlencode }}" target="_blank" rel="noopener noreferrer">Twitter</a>
          </div>
        </div>
      </header>

      <section class="audio-panel" aria-label="Episode audio">
        {% if episode.podcast_audio and episode.podcast_audio.mp3 %}
          {% include "cast/audio/audio.html" with value=episode.podcast_audio page=episode podlove_load_mode="facade" %}
        {% else %}
          <p>Audio copy pending.</p>
        {% endif %}
      </section>

      <div class="show-notes">
        {% for block in page.body %}
          <section class="block-{{ block.block_type }}">
            {% for child_block in block.value %}
              {% include_block child_block %}
            {% endfor %}
          </section>
        {% endfor %}
      </div>
    </article>
  </main>
{% endblock content %}

{% block javascript %}
  {{ block.super }}
  {% if episode.podcast_audio and episode.podcast_audio.mp3 %}
    {% vite_asset 'src/audio/podlove-player.ts' app="cast" %}
  {% endif %}
{% endblock javascript %}
```

- [ ] **Step 2: Smoke-test the detail page renders without raising**

Run: `just manage runserver` in one terminal; then `curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8000/episodes/django-tasks-jake-howard/`
Expected: `200`. Stop the dev server.

- [ ] **Step 3: Stage and request commit approval**
```bash
git add django_chat/templates/cast/django_chat/episode.html
git status --short
# Suggested commit message (commit only when the user explicitly approves):
#   "Restyle episode detail with Podlove facade and django-vite asset"
```

---

## Task 11: Update existing route tests for new markup

**Files:**
- Modify: `django_chat/imports/tests/test_sample_site_routes.py`

- [ ] **Step 1: Re-run the existing suite to see what breaks**

Run: `just test django_chat/imports/tests/test_sample_site_routes.py -x`
Expected: failures. Read each failing assertion.

- [ ] **Step 2: Update assertions that no longer hold**

In `django_chat/imports/tests/test_sample_site_routes.py`, apply these surgical changes:

**a.** In `test_imported_sample_index_renders_django_chat_theme_and_source_links`, the previous template had `Django Web Framework Podcast` as the eyebrow. The new eyebrow is `A biweekly podcast on the Django Web Framework`. Update the assertion:

```python
# old
assert "Django Web Framework Podcast" in content
# new
assert "A biweekly podcast on the Django Web Framework" in content
```

**b.** In `test_imported_sample_episode_detail_renders_without_copied_audio`, the assertion `assert "<audio" not in content` is still correct because the `<audio>` element is no longer rendered when there is no MP3. Keep it. The `Audio copy pending.` assertion also still holds. No change needed.

**c.** In `test_imported_sample_episode_detail_renders_copied_audio`, the previous test asserted `assert "<audio" in content`. The new template uses `<podlove-player>`. Replace:

```python
# old
assert "<audio" in content
assert "/media/cast_audio/django-chat-sample/django-tasks-jake-howard-" in content
# new
assert "<podlove-player" in content
assert 'data-load-mode="facade"' in content
# the MP3 URL still appears in the partial's data-* attributes / facade markup
assert "/media/cast_audio/django-chat-sample/django-tasks-jake-howard-" in content
```

If the third assertion fails (the MP3 URL isn't visible in the rendered HTML — facade mode may inline only metadata), drop that assertion and instead assert the Podlove config endpoint URL is present:

```python
assert "/cast/api/audio/" in content  # cast:api:audio_podlove_detail prefix
```

- [ ] **Step 3: Re-run and confirm green**

Run: `just test django_chat/imports/tests/test_sample_site_routes.py -x`
Expected: PASS.

- [ ] **Step 4: Stage and request commit approval**
```bash
git add django_chat/imports/tests/test_sample_site_routes.py
git status --short
# Suggested commit message (commit only when the user explicitly approves):
#   "Update route assertions for new layout and Podlove markup"
```

---

## Task 12: Add OG and favicon assertion tests

**Files:**
- Create: `django_chat/core/tests/test_template_meta.py`

- [ ] **Step 1: Write the test**

Create `django_chat/core/tests/test_template_meta.py`:

```python
from __future__ import annotations

import pytest
from django.test import Client

from django_chat.imports.import_sample import import_django_chat_sample


@pytest.mark.django_db
def test_episode_index_emits_favicon_links(client: Client) -> None:
    import_django_chat_sample()

    response = client.get("/episodes/")

    body = response.content.decode()
    assert 'rel="icon"' in body
    assert "favicon.svg" in body
    assert "favicon.ico" in body
    assert "apple-touch-icon" in body


@pytest.mark.django_db
def test_episode_index_emits_og_tags(client: Client) -> None:
    import_django_chat_sample()

    response = client.get("/episodes/")

    body = response.content.decode()
    assert 'property="og:site_name"' in body
    assert 'property="og:title"' in body
    assert 'property="og:image"' in body
    assert 'property="og:type" content="website"' in body
    assert 'name="twitter:card" content="summary_large_image"' in body


@pytest.mark.django_db
def test_episode_detail_emits_article_og_type(client: Client) -> None:
    import_django_chat_sample()

    response = client.get("/episodes/django-tasks-jake-howard/")

    body = response.content.decode()
    assert 'property="og:type" content="article"' in body


@pytest.mark.django_db
def test_episode_index_loads_self_hosted_fonts_css(client: Client) -> None:
    import_django_chat_sample()

    response = client.get("/episodes/")

    body = response.content.decode()
    assert "django_chat/css/site.css" in body
    # No third-party Google Fonts request:
    assert "fonts.googleapis.com" not in body
    assert "fonts.gstatic.com" not in body
```

- [ ] **Step 2: Run the test**

Run: `just test django_chat/core/tests/test_template_meta.py -x`
Expected: PASS.

- [ ] **Step 3: Stage and request commit approval**
```bash
git add django_chat/core/tests/test_template_meta.py
git status --short
# Suggested commit message (commit only when the user explicitly approves):
#   "Cover favicon and Open Graph metadata in template tests"
```

---

## Task 13: Restyle error pages

**Files:**
- Modify: `django_chat/templates/cast/django_chat/400.html`
- Modify: `django_chat/templates/cast/django_chat/403.html`
- Modify: `django_chat/templates/cast/django_chat/403_csrf.html`
- Modify: `django_chat/templates/cast/django_chat/404.html`
- Modify: `django_chat/templates/cast/django_chat/500.html`

- [ ] **Step 1: Rewrite each error page**

Each file gets the same skeleton. For `400.html`:

```django
{% extends "./base.html" %}
{% block title %}Bad request{% endblock title %}
{% block content %}
  <main>
    <section class="status-page">
      <h1>Bad request</h1>
      <p>The request couldn't be understood. Try again or head back to the show.</p>
      <p><a href="{% url 'django_chat_episode_index' %}">← Back to Episodes</a></p>
    </section>
  </main>
{% endblock content %}
```

`403.html`:

```django
{% extends "./base.html" %}
{% block title %}Forbidden{% endblock title %}
{% block content %}
  <main>
    <section class="status-page">
      <h1>Forbidden</h1>
      <p>You don't have permission to view this page.</p>
      <p><a href="{% url 'django_chat_episode_index' %}">← Back to Episodes</a></p>
    </section>
  </main>
{% endblock content %}
```

`403_csrf.html`:

```django
{% extends "./base.html" %}
{% block title %}CSRF verification failed{% endblock title %}
{% block content %}
  <main>
    <section class="status-page">
      <h1>CSRF verification failed</h1>
      <p>Refresh the page and try the action again.</p>
      <p><a href="{% url 'django_chat_episode_index' %}">← Back to Episodes</a></p>
    </section>
  </main>
{% endblock content %}
```

`404.html`:

```django
{% extends "./base.html" %}
{% block title %}Episode not found{% endblock title %}
{% block content %}
  <main>
    <section class="status-page">
      <h1>Episode not found</h1>
      <p>That URL doesn't match anything we host.</p>
      <p><a href="{% url 'django_chat_episode_index' %}">← Back to Episodes</a></p>
    </section>
  </main>
{% endblock content %}
```

`500.html`:

```django
{% extends "./base.html" %}
{% block title %}Server error{% endblock title %}
{% block content %}
  <main>
    <section class="status-page">
      <h1>Something went wrong on our end</h1>
      <p>The error has been logged. Try again in a moment.</p>
      <p><a href="{% url 'django_chat_episode_index' %}">← Back to Episodes</a></p>
    </section>
  </main>
{% endblock content %}
```

- [ ] **Step 2: Smoke-check 404 by hitting an unknown URL**

Run: `just runserver` (one terminal); `curl -s -o /tmp/404.html -w '%{http_code}\n' http://127.0.0.1:8000/episodes/this-does-not-exist/ && grep -c 'Episode not found' /tmp/404.html`. Stop the dev server.
Expected: `404` and `1`.

- [ ] **Step 3: Stage and request commit approval**
```bash
git add django_chat/templates/cast/django_chat/400.html \
        django_chat/templates/cast/django_chat/403.html \
        django_chat/templates/cast/django_chat/403_csrf.html \
        django_chat/templates/cast/django_chat/404.html \
        django_chat/templates/cast/django_chat/500.html
git status --short
# Suggested commit message (commit only when the user explicitly approves):
#   "Brand error pages with Django Chat shell"
```

---

## Task 14: Run the full quality-gate suite

**Files:**
- None — verification only

- [ ] **Step 1: Run lint**

Run: `just lint`
Expected: clean exit (no warnings/errors). If `import sorting` warnings appear in `views.py`, run `just format` then `just lint` again.

- [ ] **Step 2: Run typecheck**

Run: `just typecheck`
Expected: clean. The new `EPISODES_PER_PAGE` constant and the dict literal in `render(...)` should type-check. If `ty` complains about `paginator.get_page` return type, narrow to `Page` explicitly via `from django.core.paginator import Page` and annotate `page_obj: Page = paginator.get_page(page_number)`.

- [ ] **Step 3: Run the whole test suite**

Run: `just test`
Expected: all tests pass.

- [ ] **Step 4: Run hooks**

Run: `uv run prek run -a` (the configured hook runner per `prek.toml`).
Expected: no failures.

- [ ] **Step 5: Stage auto-fixes and request commit approval**

```bash
git status --short
# if anything is modified by formatters/hooks:
git add -p
git status --short
# Suggested commit message (commit only when the user explicitly approves):
#   "Apply formatter and hook fixes"
```

---

## Task 15: Visual verification on the running dev server

**Files:**
- Create: `scripts/visual-diff.mjs` (one-off helper, not committed unless useful)

- [ ] **Step 1: Start the dev server in background**

Run: `just runserver` in a separate terminal and leave it running.

- [ ] **Step 2: Render screenshots from the local site**

Reuse the Playwright setup from `/tmp/djangochat-screenshots.mjs` (created during brainstorming). Run:

```bash
node - <<'JS'
import { chromium } from "/tmp/node_modules/playwright/index.mjs";
const targets = [
  { url: "http://127.0.0.1:8000/episodes/", out: "/tmp/local-list.png" },
  { url: "http://127.0.0.1:8000/episodes/django-tasks-jake-howard/", out: "/tmp/local-detail.png" },
];
const browser = await chromium.launch();
const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
for (const t of targets) {
  const page = await context.newPage();
  await page.goto(t.url, { waitUntil: "networkidle", timeout: 30000 });
  await page.waitForTimeout(800);
  await page.screenshot({ path: t.out, fullPage: true });
  await page.close();
}
await browser.close();
JS
ls -lh /tmp/local-list.png /tmp/local-detail.png
```

Expected: two PNG files written. Open them alongside `/tmp/djangochat-home.png` and `/tmp/djangochat-episode.png` (saved during brainstorming) and confirm the new staging visually rhymes with djangochat.com — same palette, same hero shape, same row layout.

- [ ] **Step 3: Stop the dev server**

In its terminal, `Ctrl+C`.

- [ ] **Step 4 (optional, skip if not deploying yet): Lighthouse on staging**

After the next staging deploy, run Chrome's Lighthouse against `https://djangochat.staging.django-cast.com/episodes/django-tasks-jake-howard/`. Expected: performance score > 80. This is a sanity check, not a regression gate.

---

## Task 16: Close out the implementation status doc

**Files:**
- Modify: `docs/implementation-status.md`

- [ ] **Step 1: Update the status entries**

In `docs/implementation-status.md`:

- Mark item **6** as having received a polish pass (append a sentence: "Polished `2026-04-26`: spirit-parity layout with djangochat.com, Podlove player via django-vite, search/facets, OG metadata, favicon. See `docs/superpowers/specs/2026-04-26-visual-polish-design.md`.").
- In **Open Work**, remove item **1 (Visual polish pass)** — it just landed. The list renumbers naturally.
- In **Next Action**, replace the "Visual polish on the staging templates" block with a pointer to the next item in the queue: the transcript demo.

The file should still be a thin pointer; no PRD content moves into it.

- [ ] **Step 2: Stage and request commit approval**
```bash
git add docs/implementation-status.md
git status --short
# Suggested commit message (commit only when the user explicitly approves):
#   "Close visual polish pass in implementation status"
```

---

## Verification checklist (run before declaring done)

- [ ] `just check` passes (lint + format-check + typecheck + test)
- [ ] `uv run prek run -a` is clean
- [ ] Local screenshots at `/tmp/local-list.png` and `/tmp/local-detail.png` look like the show
- [ ] No unexpected entries in `git status --short`; all intended changes are staged or committed with approval
- [ ] `docs/implementation-status.md` reflects the close-out
