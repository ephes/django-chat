# Django Chat

This repository contains the self-hosted Django Chat site scaffold. The site is
built with Django, Wagtail, and django-cast, using Python Podcast only as a
structural reference for local development ergonomics.

Current status: initial runnable scaffold for a staging proof of concept. The
planning source of truth is
[`2026-04-18_django-chat_research.md`](2026-04-18_django-chat_research.md).

## Local Development

This project targets Python 3.14.4. `uv` reads the `.python-version` file and
can download the matching interpreter when needed.

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

Run the local development server:

```sh
just runserver
```

The default Django settings module for `manage.py` is
`config.settings.local`. Local and test settings use SQLite so the scaffold can
run without PostgreSQL or other services.

## Scope

This slice intentionally does not include import commands, S3 media copy,
transcript worker settings, deployment commands, host review docs, or staging
URLs. Those are later implementation slices from the research PRD.

Private deployment configuration and secrets are intentionally not stored in
this repo. Do not commit real Django secret keys, database passwords, S3
credentials, Sentry DSNs, Mailgun keys, admin passwords, or decrypted secret
files.
