# Django Chat

This repository contains the self-hosted Django Chat site scaffold. The site is
built with Django, Wagtail, and django-cast, using Python Podcast only as a
structural reference for local development ergonomics.

Current status: runnable local scaffold with development tooling, a
fixture-backed source parser, and an idempotent local sample import that creates
django-cast podcast and episode pages without copying media. The planning
source of truth is
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

Run all local quality checks:

```sh
just check
```

Run the local development server:

```sh
just runserver
```

The default Django settings module for `manage.py` is
`config.settings.local`. Local and test settings use SQLite so the scaffold can
run without PostgreSQL or other services.

## Scope

This slice intentionally includes only a small fixture-backed database/page
import for local proof of idempotency. It does not include full catalog import,
S3 media copy, transcript conversion, a transcript worker service, templates,
route compatibility, deployment commands, host review docs, or staging URLs.
Those are later implementation slices from the research PRD.

Deployment configuration is not implemented yet. The current plan is to keep
Django Chat-specific deployment code in this repo and store only
SOPS/age-encrypted environment secret files here. Do not commit decrypted
Django secret keys, database passwords, S3 credentials, Sentry DSNs, Mailgun
keys, admin passwords, or age private keys.
