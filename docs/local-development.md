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

## Boundaries

Private deployment configuration and secrets stay outside this shareable app
repo. This slice does not include import commands, S3 media copy, transcript
conversion, a transcript worker service, deployment commands, host review docs,
or staging URLs; those are later implementation slices from the research PRD.
