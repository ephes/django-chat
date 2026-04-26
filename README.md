# Django Chat

This repository contains the self-hosted Django Chat site scaffold. The site is
built with Django, Wagtail, and django-cast, using Python Podcast only as a
structural reference for local development ergonomics.

Current status: runnable local scaffold with development tooling, a
fixture-backed source parser, an idempotent sample import, a repeatable live
full-catalog import command with opt-in streaming audio copy, explicit
sample audio-copy support for configured media storage, and a basic Django
Chat-branded browsing experience for imported episodes, plus a smoke-level
feed comparison for the fixture-backed sample and local catalog performance
measurement tooling. The repo also contains
self-contained deployment scaffolding under `deploy/` and host review docs for
the first staging path. Staging is live at
`https://djangochat.staging.django-cast.com` with the fixture-backed sample
imported and Wagtail admin mounted at
`https://djangochat.staging.django-cast.com/cms/`. Sample audio is copied to
the configured S3 bucket and served through the public media host, so episode
detail pages render a working `<audio>` element. Current staging is suitable
for internal smoke review, but not yet ready for full host review of the
representative show until the live catalog command has been run on staging and
the remaining RSS-discovery and transcript-demo gaps are closed. No production
deployment has been performed. The planning source
of truth is
[`2026-04-18_django-chat_research.md`](2026-04-18_django-chat_research.md).

## Local Development

This project targets Python 3.14.4. `uv` reads the `.python-version` file and
can download the matching interpreter when needed. See
[`docs/local-development.md`](docs/local-development.md) for the full local
workflow, environment file expectations, tooling commands, and hook setup.

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

Measure generated feed timing/item count and episode-list timing/query count
after importing data:

```sh
just manage measure_django_chat_catalog
```

Run all local quality checks:

```sh
just check
```

Run the local development server:

```sh
just runserver
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
[`docs/staging-differences.md`](docs/staging-differences.md).

Current staging smoke review uses:

- Site: `https://djangochat.staging.django-cast.com/`
- Wagtail admin: `https://djangochat.staging.django-cast.com/cms/`

The initial host-review admin credential is a staging-only bootstrap secret
kept outside the repository and outside repo-managed SOPS files. Share or
rotate it only through the agreed secure channel.

For the current shipped/open-work picture and the next-action target, see
[`docs/implementation-status.md`](docs/implementation-status.md).

## Scope

This slice includes a small fixture-backed database/page import, a live
full-catalog metadata import path, opt-in streaming catalog audio copy, basic
Django Chat django-cast templates, imported menu/social/distribution link
rendering, local URL compatibility for `/`, `/episodes/`, and
`/episodes/<slug>/`, a local smoke-level feed comparison for the imported
sample, catalog performance measurement tooling, and deployment scaffolding.

It does not include RSS-discovery page work, transcript conversion, an enabled
transcript worker service, exhaustive production feed parity, real production
deployment, production DNS changes, or feed redirects. Sample audio has been
copied into staging and is reachable through the public media host, so internal
review can inspect the deployed site/CMS and end-to-end playback before the
full host-review gate.

Do not commit decrypted Django secret keys, database passwords, S3 credentials,
Sentry DSNs, Mailgun keys, admin passwords, age private keys, real MP3s, large
fixtures, or Python Podcast-specific deployment details.
