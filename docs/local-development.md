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

Copy audio for the same eight fixture-backed sample episodes, and download
the show artwork as the Podcast page's `cover_image` so the Podlove player
chrome has an episode poster to display:

```sh
just manage import_django_chat_sample --copy-audio --copy-cover-image
```

The audio-copy path reuses the source metadata rows from the normal sample
import. For each episode, it chooses the Simplecast direct audio URL when
available, otherwise the Simplecast enclosure URL, otherwise the RSS enclosure
URL. It stores the downloaded file through Django's configured default media
storage, creates or updates a `cast.Audio` row, and attaches that row to
`cast.Episode.podcast_audio`.

`--copy-cover-image` downloads the show artwork URL recorded in
`PodcastSourceMetadata.image_url`, creates a `wagtail.images.Image`, and
attaches it to `Podcast.cover_image`. The Podlove player surfaces this as the
per-episode cover (Simplecast does not expose per-episode artwork, so the
show artwork is reused on every episode — same as djangochat.com). The flag
is idempotent: subsequent runs do nothing when `cover_image` is already set.

Repeated `--copy-audio` runs are idempotent for the sample: existing audio-copy
metadata rows are reused, files are not downloaded again when the source URL and
stored file name still match and the stored file exists, and no duplicate
episode pages, source metadata, link metadata, audio rows, or transcript rows
are created.

Both `--copy-audio` and `--copy-cover-image` download real bytes when run
without fake downloaders, so use them deliberately. Tests use in-memory
fakes and never require live network access or real S3.

## Full Catalog Import

The live catalog importer reads the canonical RSS feed and enriches it from
the public Simplecast podcast/site/distribution/episode endpoints when those
responses expose data. It does not use committed fixtures and does not require
Simplecast credentials.

Run a limited metadata import for local exercise:

```sh
just manage import_django_chat_catalog --max-episodes 3
```

Plan the same limited import and roll back database writes:

```sh
just manage import_django_chat_catalog --dry-run --max-episodes 3
```

Import metadata for the current full public catalog:

```sh
just manage import_django_chat_catalog
```

Attach the show artwork while importing metadata:

```sh
just manage import_django_chat_catalog --copy-cover-image
```

Copy audio only when you intend to transfer the catalog media. The full public
catalog was observed at about 11 GB in the research PRD, so do not run this
casually on local or staging:

```sh
just manage import_django_chat_catalog --copy-cover-image --copy-audio
```

Safe rerun behavior:

- Podcast, episode, source metadata, source link, and audio metadata rows are
  updated in place using RSS GUIDs, Simplecast IDs/slugs, and source-link keys.
- Audio copy uses streaming file transfer into Django storage, not whole-MP3
  in-memory reads.
- Existing copied audio is skipped when the stored file still exists and the
  recorded source URL still matches.
- Re-running the command re-fetches RSS and Simplecast metadata; it does not
  assume previous endpoint responses are still current.
- `--copy-cover-image` skips the download once `Podcast.cover_image` is set.

Operator controls:

- `--max-episodes N` limits RSS/list/detail import to the latest N episodes.
- `--timeout SECONDS` controls per-request source and media timeouts.
- `--simplecast-page-size N` controls the initial episode-list page size;
  later pages follow Simplecast's returned `next` URL.
- `--simplecast-max-pages N` stops Simplecast pagination after N pages.
- `--dry-run` fetches source data and rolls back database writes; it cannot be
  combined with `--copy-audio` or `--copy-cover-image`.

Tests use fake fetchers and fake streaming downloaders. Automated tests never
hit the live feed, Simplecast, real S3, or real MP3 files.

## Feed Smoke Check

Slice 7 adds a deterministic local feed smoke check for the fixture-backed
sample. After running migrations and importing the sample with copied audio,
run:

```sh
just compare-feed
```

This invokes `compare_django_chat_sample_feed`, fetches the local
django-cast podcast feed route `/episodes/feed/podcast/mp3/rss.xml` through
Django, and compares it to the committed Simplecast RSS fixture at
`django_chat/imports/tests/fixtures/django_chat_source/rss_feed.xml`. The
command does not use live network access.

The strict smoke checks cover:

- show/feed title
- sample episode count
- item GUID order and GUID values
- item titles
- item publication dates
- item durations when both feeds expose them
- enclosure presence and media type
- generated enclosure length against the copied byte size recorded in
  `EpisodeAudioImportMetadata.copied_byte_size`

Metadata-only imports are expected to fail this check with an actionable
message. django-cast excludes episodes without `podcast_audio` from podcast
feeds, so run:

```sh
just manage import_django_chat_sample --copy-audio --copy-cover-image
just compare-feed
```

The enclosure length policy is explicit: strict checking uses the bytes of the
file copied into configured media storage, not the source-reported Simplecast
byte size. `EpisodeAudioImportMetadata.source_byte_size` remains the source RSS
or Simplecast byte count, while `copied_byte_size` records the actual stored
file size. When tests use fake in-memory audio, copied sizes intentionally
differ from Simplecast source sizes; the feed smoke check reports that as a
warning, not a failure, as long as the generated feed length matches copied
bytes.

Generated enclosure URLs are also warning-only when they differ from the
Simplecast fixture, because local filesystem media or a Django Chat S3 bucket
will naturally produce different URLs from Simplecast/Podtrac. Production
migration hardening still needs exhaustive feed parity, artwork and namespace
validation, full-catalog checks, feed redirect or new-feed-url decisions, and
podcast-client testing before any cutover.

## Catalog Performance Measurement

After importing sample or catalog data, measure the generated RSS feed and the
episode index through Django's test client:

```sh
just manage measure_django_chat_catalog
```

The command reports:

- generated podcast RSS route status, timing, item count, and query count
- latest-entries RSS route status, timing, item count, and query count
- live imported episode audio completeness for the selected podcast slug
- `/episodes/` response status, timing, and query count

Run it after a full catalog import for meaningful scale data. For
representative host review, `missing_audio` must be `0`; metadata-only catalog
imports and limited local smoke imports may report missing audio until
`--copy-audio` has been run deliberately. The limited three-episode exercise is
useful for command validation only. Lighthouse and Web Vitals checks remain
manual browser checks against deployed staging once the full catalog is
present. The command expects the selected podcast slug to exist and will raise
`Podcast.DoesNotExist` otherwise; run a sample or catalog import before
measuring a fresh database.

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
`DJANGO_SECRET_KEY` in `.env` for local overrides. Deployment settings use
`config.settings.production` and SOPS/age-encrypted environment files under
`deploy/secrets/`; see `docs/deployment.md` and `docs/operations-boundary.md`.

`config.wsgi` and `config.asgi` currently default to `config.settings.local`
only for local scaffold ergonomics. The deployment role sets
`DJANGO_SETTINGS_MODULE=config.settings.production` in the rendered server
environment.

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
Deployment-specific bucket creation and real SOPS/age secret files remain
operator-owned and must not be committed decrypted.

## Deployment Commands

Deployment is separate from local development, but the command surface is
available from this repo:

```sh
just deploy-bootstrap
just deploy-bootstrap-target staging
just deploy-static-check
just deploy-check
just deploy-staging
just deploy-production
```

`just deploy-bootstrap` installs Ansible dependencies under `deploy/.ansible/`.
`just deploy-bootstrap-target <group>` runs only the baseline host tasks against
one inventory group, such as `staging` or `production`, and does not deploy the
app. Valid target groups are `staging`, `production`, and `django_chat`.
`just deploy-static-check` verifies the package-bundled static manifests needed
by deployment. `just deploy-check` runs those checks plus Ansible syntax checks
without contacting deployment hosts. The staging and production deploy commands
require real inventory values, encrypted SOPS secrets, an age private key, and
SSH/DNS readiness.

## Boundaries

This repo contains Django Chat deployment scaffolding, live staging inventory,
production placeholder inventory, public deployment vars, and SOPS secret
examples. Decrypted secrets, age private keys, real host credentials, staging
bootstrap password handoff files, and private operator notes stay outside the
repo.

This repo now includes host review docs for the live staging path at
`https://djangochat.staging.django-cast.com`, but it does not include
exhaustive production feed parity, production DNS changes, feed redirects, or
production migration. Live staging has full-catalog metadata, copied audio for
all live imported episodes, a Voxhelm-generated transcript demo at
`/episodes/preview/transcript/`, and an enabled `cast_transcripts` worker for
Wagtail-triggered transcript generation. Full host review should follow the
current next-action guidance in
`docs/implementation-status.md`.
