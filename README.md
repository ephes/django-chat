# Django Chat

This repository contains the self-hosted Django Chat site scaffold. The site is
built with Django, Wagtail, and django-cast, using Python Podcast only as a
structural reference for local development ergonomics.

Current status: runnable local scaffold with development tooling, source
parsers, idempotent sample and full-catalog import commands, opt-in streaming
audio copy, a Django Chat-branded browsing experience for imported episodes,
feed comparison and catalog measurement tooling, self-contained deployment
scaffolding under `deploy/`, and host review docs for staging. Staging is live
at `https://djangochat.staging.django-cast.com` with full-catalog metadata,
copied audio for all live imported episodes, generated RSS routes, Wagtail
admin at `https://djangochat.staging.django-cast.com/cms/`, and a
Voxhelm-generated transcript demo at `/episodes/preview/transcript/`. No
production deployment has been performed. The planning source of truth is
[`2026-04-18_django-chat_research.md`](2026-04-18_django-chat_research.md).

## Local Development

This project targets Python 3.14.4. `uv` reads the `.python-version` file and
can download the matching interpreter when needed. See
[`docs/local-development.md`](docs/local-development.md) for the full local
workflow, environment file expectations, tooling commands, and hook setup.

Frontend conventions — cascade-layer order, token naming, class naming, JS
hooks, and Safari 16 `color-mix()` fallbacks — are documented in
[`docs/css-architecture.md`](docs/css-architecture.md).

The `docs/` tree renders as a documentation site with [Zensical](https://zensical.org).
Serve it locally with `just docs` (defaults to `localhost:8000`; pass a port,
e.g. `just docs 8001`), or build a static copy into `site/` with `just docs-build`.

Install dependencies:

```sh
just install
```

Run Django checks:

```sh
just manage check
```

Create or update the local SQLite database before using the Wagtail admin:

```sh
just manage migrate
```

Run tests:

```sh
just test
```

Import the local fixture-backed podcast/episode sample:

```sh
just manage import_django_chat_sample
```

Copy audio for that same small sample into the configured media storage:

```sh
just manage import_django_chat_sample --copy-audio
```

Run a safe limited live-catalog import from the public RSS/Simplecast sources:

```sh
just manage import_django_chat_catalog --max-episodes 3
```

Plan the live catalog without keeping database changes:

```sh
just manage import_django_chat_catalog --dry-run --max-episodes 3
```

Copying full-catalog audio is opt-in and can transfer about 11 GB:

```sh
just manage import_django_chat_catalog --copy-cover-image --copy-audio
```

Compare the generated local django-cast podcast feed for the imported sample
against the committed Simplecast RSS fixture:

```sh
just compare-feed
```

Run strict live feed parity for the production cutover: compare the live
Simplecast feed against a candidate self-hosted feed URL (the app-served
django-cast feed route on staging or production). Both feeds are fetched through
the import SSRF guard; the command exits non-zero on any subscriber-affecting
regression:

```sh
just compare-live-feed --candidate-url https://djangochat.com/episodes/feed/podcast/mp3/rss.xml
```

Measure generated feed timing/item count and episode-list timing/query count
after importing data:

```sh
just manage measure_django_chat_catalog
```

Import django-cast transcript artifacts from the current staging system:

```sh
just import-staging-transcripts
```

Limit that to one episode with `--slug django-tasks-jake-howard`. This reads
the staging Podlove player API and writes local Podlove JSON, WebVTT, and DOTe
transcript files into the same S3/CloudFront media backend used by `just dev`;
it does not import Simplecast transcript HTML. Use this `just` recipe rather
than the lower-level `just manage import_django_chat_staging_transcripts`
command for normal local review, because the recipe supplies the staging media
storage environment.

When S3 media storage is enabled, the django-cast `cast_private_media` storage
alias is also pointed at the same durable S3 bucket/media host under a separate
object prefix. This guards future django-cast transcript-storage migrations
from moving transcript artifacts to a local private-media directory or deleting
a copied destination by removing the original public-media key.

Run all local quality checks:

```sh
just check
```

Run the local development server. This uses the staging S3/CloudFront media
backend by default so imported Wagtail images and episode media render locally:

```sh
just dev
```

After importing the sample, open `http://localhost:8000/episodes/` to browse
the sample episode index. `http://localhost:8000/` redirects to `/episodes/`,
and imported episode detail pages keep the current public shape
`/episodes/<slug>/`.

The default Django settings module for `manage.py` is
`config.settings.local`. Local and test settings use SQLite so the scaffold can
run without PostgreSQL or other services.

## Deployment Scaffolding

Deployment is documented in
[`docs/deployment.md`](docs/deployment.md), with the security and ownership
boundary in
[`docs/operations-boundary.md`](docs/operations-boundary.md).

Bootstrap repo-local Ansible dependencies:

```sh
just deploy-bootstrap
```

Run offline deployment checks:

```sh
just deploy-check
```

Run the clean-VPS baseline tasks for one inventory group without deploying the
app:

```sh
just deploy-bootstrap-target staging
```

Run the staging or production deployment playbooks when the target inventory,
SOPS/age secrets, and operator access are in place:

```sh
just deploy-staging
just deploy-production
```

The deploy commands do not require `ops-control`. They install a pinned
`ops-library` collection through Ansible Galaxy and load environment secrets
from `deploy/secrets/staging.sops.yml` or
`deploy/secrets/production.sops.yml`. Those encrypted secret paths are ignored,
and decrypted secret files must stay out of the repository.

## Host Review

The host review workflow is documented in
[`docs/host-review-guide.md`](docs/host-review-guide.md), and known differences
between staging, Simplecast, and a future production migration are documented in
[`docs/staging-differences.md`](docs/staging-differences.md). Production
migration risks and cutover decisions are tracked separately in
[`docs/production-migration-notes.md`](docs/production-migration-notes.md),
with feed-specific failure modes and the proposed feed cutover plan in
[`docs/feed-cutover-analysis.md`](docs/feed-cutover-analysis.md).

Current staging smoke review uses:

- Site: `https://djangochat.staging.django-cast.com/`
- Wagtail admin: `https://djangochat.staging.django-cast.com/cms/`

The initial host-review admin credential is a staging-only bootstrap secret
kept outside the repository and outside repo-managed SOPS files. Share or
rotate it only through the agreed secure channel.

For the current shipped/open-work picture and the next-action target, see
[`docs/implementation-status.md`](docs/implementation-status.md).

Episode contributor snippets and the diarized transcript speaker-label workflow
(including the django-cast `develop` dependency pin, migrations, Wagtail editor
steps, and staging verification) are documented in
[`docs/contributors-and-diarization.md`](docs/contributors-and-diarization.md).

## Scope

This slice includes a small fixture-backed database/page import, a live
full-catalog metadata import path, opt-in streaming catalog audio copy, basic
Django Chat django-cast templates, imported menu/social/distribution link
rendering on the episode overview, local URL compatibility for `/`,
`/episodes/`, and `/episodes/<slug>/`, a branded RSS-discovery page at
`/episodes/feed/` with page-head RSS auto-discovery links, a local
smoke-level feed comparison for the
imported sample, catalog performance measurement tooling, and deployment
scaffolding.

It does not include full-catalog transcript conversion, a verified production
feed-parity run, real production deployment, production DNS changes, podcast
directory updates, Simplecast retirement, or production URL redirects. Full-catalog audio has been copied into staging and
is reachable through the public media host, so internal review can inspect the
deployed site/CMS, Wagtail-triggered transcript generation, and end-to-end
playback before the full host-review gate.

Do not commit decrypted Django secret keys, database passwords, S3 credentials,
Sentry DSNs, Mailgun keys, admin passwords, age private keys, real MP3s, large
fixtures, or Python Podcast-specific deployment details.
