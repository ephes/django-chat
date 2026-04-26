# Django Chat

This repository contains the self-hosted Django Chat site scaffold. The site is
built with Django, Wagtail, and django-cast, using Python Podcast only as a
structural reference for local development ergonomics.

Current status: runnable local scaffold with development tooling, a
fixture-backed source parser, an idempotent sample import, explicit sample
audio-copy support for configured media storage, and a basic Django
Chat-branded browsing experience for the imported sample, plus a smoke-level
feed comparison for the fixture-backed sample. The repo also contains
self-contained deployment scaffolding under `deploy/` and host review docs for
the first staging path. Staging is live at
`https://djangochat.staging.django-cast.com` with the fixture-backed sample
imported and Wagtail admin mounted at
`https://djangochat.staging.django-cast.com/cms/`. Sample audio is copied to
the configured S3 bucket and served through the public media host, so episode
detail pages render a working `<audio>` element. No production deployment has
been performed. The planning source of truth is
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

Compare the generated local django-cast podcast feed for the imported sample
against the committed Simplecast RSS fixture:

```sh
just compare-feed
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

Staging review uses:

- Site: `https://djangochat.staging.django-cast.com/`
- Wagtail admin: `https://djangochat.staging.django-cast.com/cms/`

The initial host-review admin credential is a staging-only bootstrap secret
kept outside the repository and outside repo-managed SOPS files. Share or
rotate it only through the agreed secure channel.

## Scope

This slice includes a small fixture-backed database/page import, opt-in audio
copy, basic Django Chat django-cast templates, fixture-derived
menu/social/distribution link rendering, local URL compatibility for `/`,
`/episodes/`, and `/episodes/<slug>/`, a local smoke-level feed comparison for
the imported sample, and deployment scaffolding.

It does not include full catalog import, transcript conversion, an enabled
transcript worker service, exhaustive production feed parity, real production
deployment, production DNS changes, or feed redirects. Sample audio has been
copied into staging and is reachable through the public media host, so host
review can inspect both the site/CMS and end-to-end playback.

Do not commit decrypted Django secret keys, database passwords, S3 credentials,
Sentry DSNs, Mailgun keys, admin passwords, age private keys, real MP3s, large
fixtures, or Python Podcast-specific deployment details.
