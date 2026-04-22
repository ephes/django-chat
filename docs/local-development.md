# Local Development

Django Chat targets Python 3.14.4 and uses `uv` for dependency management.
The `.python-version` file pins the interpreter expected by local commands.

## Setup

Install or update dependencies:

```sh
just install
```

Create or update the local SQLite database:

```sh
just manage migrate
```

Run Django management commands through `just manage`:

```sh
just manage check
just manage createsuperuser
```

Run the development server:

```sh
just runserver
```

The default settings module for `manage.py` is `config.settings.local`.
Local and test settings use SQLite and do not require PostgreSQL or any other
external service.

## Tests And Quality Checks

Run tests:

```sh
just test
```

Run linting:

```sh
just lint
```

Apply formatting:

```sh
just format
```

Check formatting without writing changes:

```sh
just format-check
```

Run smoke-level typechecking for local project code:

```sh
just typecheck
```

Run the combined local confidence check:

```sh
just check
```

`just check` runs linting, format checking, typechecking, and tests. Typechecking
is intentionally scoped to `config`, `django_chat`, and `manage.py` for now so
the command checks local code without taking on Django, Wagtail, or django-cast
internals as a strict typing target.

## Git Hooks

This repo uses `prek` as the hook runner. Install the hooks after dependencies
are available:

```sh
uv run prek install
```

Run the configured hooks across the repository:

```sh
uv run prek run --all-files
```

The hook configuration runs basic file hygiene checks, Ruff lint/format hooks,
and the same scoped `ty` typecheck used by `just typecheck`.

Ruff skips Django migration files. Once app migrations exist, they should stay
reviewable but should not drive lint or format churn from generated code.

## Source Data Fixtures

Slice 3 includes a read-only parser foundation for public Django Chat source
data. Tests parse committed fixtures from
`django_chat/imports/tests/fixtures/django_chat_source/` and do not require
network access.

The fixture set contains a latest/oldest sample from the canonical RSS feed,
minimized Simplecast podcast metadata, latest and oldest episode-list pages,
representative episode detail responses with transcript HTML where Simplecast
exposes it, site menu/social links, and distribution links.

Refresh the fixtures only when intentionally updating the source-data baseline:

```sh
just manage capture_django_chat_source_fixtures --force
```

The capture command fetches public unauthenticated URLs and writes fixture
files only; it does not create database rows, Wagtail pages, django-cast
objects, media files, S3 objects, or transcript conversions. Review refreshed
fixtures before committing them and keep only public, non-secret source data.

## Sample Import

The sample import adds a write-side local import for the committed source
fixture sample.
Run migrations first so the local SQLite database has the source metadata
tables:

```sh
just manage migrate
```

Import or update the Django Chat podcast page plus the representative episode
sample:

```sh
just manage import_django_chat_sample
```

The command reads
`django_chat/imports/tests/fixtures/django_chat_source/` by default and does
not use network access. It imports the latest five and oldest three fixture
episodes, enriches the available Simplecast detail fixtures, and creates or
updates one `cast.Podcast` page and eight `cast.Episode` pages. It stores RSS
GUIDs, Simplecast IDs and slugs, episode numbers, source URLs, original
enclosure URLs, duration, descriptions, long descriptions, and transcript HTML
in local source metadata rows so repeated runs do not duplicate pages or
metadata. It also stores fixture-derived Simplecast menu, social, and
distribution links in local metadata rows for template rendering.

The command creates a local `django-chat-importer` user with an unusable
password when no existing import user is available. Imported sample pages use
that user as their owner, and the audio-copy path reuses it for `Audio.user`.

Imported pages use the Django Chat django-cast theme (`cast/django_chat/...`).
The imported podcast index is available at `/episodes/`, imported episode
detail pages keep `/episodes/<slug>/`, and `/` redirects to `/episodes/`.
The `/episodes/` index is served by a small project view so metadata-only
sample imports remain browseable before audio has been copied; episode detail
pages and feed URLs still use django-cast/Wagtail routes.
Run the development server after importing the sample:

```sh
just runserver
```

Then browse:

- `http://localhost:8000/` redirects to the sample episode index.
- `http://localhost:8000/episodes/` renders the Django Chat-branded index.
- `http://localhost:8000/episodes/django-tasks-jake-howard/` renders an
  imported episode detail page.

The sample import intentionally does not download, stream, copy, or attach MP3
files unless audio copying is requested explicitly. Original RSS and Simplecast
enclosure/audio URLs are stored in metadata, and Simplecast transcript HTML is
preserved in metadata only for later conversion or publishing work.

Copy audio for the same eight fixture-backed sample episodes:

```sh
just manage import_django_chat_sample --copy-audio
```

The audio-copy path reuses the source metadata rows from the normal sample
import. For each episode, it chooses the Simplecast direct audio URL when
available, otherwise the Simplecast enclosure URL, otherwise the RSS enclosure
URL. It stores the downloaded file through Django's configured default media
storage, creates or updates a `cast.Audio` row, and attaches that row to
`cast.Episode.podcast_audio`.

Repeated `--copy-audio` runs are idempotent for the sample: existing audio-copy
metadata rows are reused, files are not downloaded again when the source URL and
stored file name still match and the stored file exists, and no duplicate
episode pages, source metadata, link metadata, audio rows, or transcript rows
are created.

The sample audio command downloads real MP3s when run without a fake downloader,
so use it deliberately. Tests use in-memory fake audio and never require live
network access or real S3.

## Environment Files

Local settings support a private `.env` file in the repository root. Start from
the safe placeholders in `.env.example` if you need local overrides:

```sh
DJANGO_READ_DOT_ENV_FILE=True
DJANGO_DEBUG=True
DJANGO_SECRET_KEY=change-me-for-local-development-only
# DJANGO_SETTINGS_MODULE=config.settings.local
# DJANGO_CHAT_WAGTAIL_ADMIN_BASE_URL=http://localhost:8000/cms/
# DATABASE_URL=sqlite:///db.sqlite3
```

`manage.py` defaults to `config.settings.local`, and pytest uses
`config.settings.test` from `pyproject.toml`. Most local development should not
need to set `DJANGO_SETTINGS_MODULE` explicitly.

Do not commit `.env`, `.env.*`, real secrets, or environment-specific
credentials. Test settings disable `.env` loading so local development values do
not leak into `pytest` runs.

`config.settings.local` includes a committed development-only fallback
`DJANGO_SECRET_KEY` so the scaffold runs without private setup. Use
`DJANGO_SECRET_KEY` in `.env` for local overrides. Non-local deployment settings
and secrets are intentionally deferred to the deployment slice.

`config.wsgi` and `config.asgi` currently default to `config.settings.local`
only for local scaffold ergonomics. Deployment settings and process-level
`DJANGO_SETTINGS_MODULE` are intentionally deferred until deployment commands
and environment-specific settings are added.

`WAGTAILADMIN_BASE_URL` defaults to `http://localhost:8000/cms/` for local
development. Staging and production must set
`DJANGO_CHAT_WAGTAIL_ADMIN_BASE_URL` when those environments are introduced.

## Media Storage

Local and test settings use filesystem media storage by default. S3-compatible
media storage is opt-in through environment variables and does not require or
ship any credentials in the repository.

Set `DJANGO_CHAT_MEDIA_STORAGE_BACKEND=s3` only when you have a
Django Chat-specific bucket and access keys:

```sh
DJANGO_CHAT_MEDIA_STORAGE_BACKEND=s3
DJANGO_CHAT_S3_ACCESS_KEY_ID=...
DJANGO_CHAT_S3_SECRET_ACCESS_KEY=...
DJANGO_CHAT_S3_STORAGE_BUCKET_NAME=...
# Optional, depending on provider and serving setup:
# DJANGO_CHAT_S3_ENDPOINT_URL=https://s3.example.com
# DJANGO_CHAT_S3_REGION_NAME=eu-central-1
# DJANGO_CHAT_S3_CUSTOM_DOMAIN=media.djangochat.example.com
# DJANGO_CHAT_MEDIA_URL=https://media.djangochat.example.com/
# DJANGO_CHAT_S3_ADDRESSING_STYLE=virtual
# DJANGO_CHAT_S3_SIGNATURE_VERSION=s3v4
# DJANGO_CHAT_S3_QUERYSTRING_AUTH=False
# DJANGO_CHAT_S3_FILE_OVERWRITE=False
# DJANGO_CHAT_S3_DEFAULT_ACL=
# DJANGO_CHAT_S3_CACHE_CONTROL=max-age=604800, s-maxage=604800, must-revalidate
```

Do not reuse Python Podcast media buckets or credentials for Django Chat.
Deployment-specific bucket creation, SOPS/age secret files, and operations docs
are intentionally deferred to the deployment slice.

## Boundaries

Private deployment configuration and secrets stay outside this shareable app
repo. This slice includes only a local fixture-backed sample import, explicit
sample audio copy, basic local templates, fixture-derived link rendering, and
current local URL compatibility. It does not include full catalog import,
transcript conversion, a transcript worker service, feed parity checks,
deployment commands, host review docs, or staging URLs. Those are later
implementation slices from the research PRD.
