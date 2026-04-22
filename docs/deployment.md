# Deployment

Django Chat deployment scaffolding lives in `deploy/` and is intentionally
self-contained. It installs Ansible dependencies from
`deploy/requirements.yml`, including a pinned `ops-library` collection, rather
than requiring `ops-control` or a manual local role checkout.

## Commands

Install Ansible dependencies locally:

```sh
just deploy-bootstrap
```

Run local deployment checks without contacting a host:

```sh
just deploy-check
```

Run clean-VPS baseline tasks for one inventory group without deploying the app:

```sh
just deploy-bootstrap-target staging
```

Use `staging`, `production`, or the parent `django_chat` group as the target.

Deploy staging:

```sh
just deploy-staging
```

Deploy production:

```sh
just deploy-production
```

`deploy-bootstrap-target` runs only `deploy/bootstrap.yml` for the requested
inventory group. `deploy-staging` and `deploy-production` run
`deploy-static-check` first, then `deploy-bootstrap`, then `ansible-playbook`.
They do not require `ops-control`.

## Ansible Dependencies

`deploy/requirements.yml` installs:

- `local.ops_library` from `https://github.com/ephes/ops-library.git` pinned to
  commit `39aaa0e3de8a99e07f4ac6642cae01518e8a043e`
- `community.postgresql` pinned to `4.2.0`
- `community.general` pinned to `12.6.0`
- `community.sops` pinned to `2.3.0`
- `ansible.posix` pinned to `2.1.0`

Dependencies are installed under `deploy/.ansible/`, which is ignored by Git.

## Inventory And Vars

Committed inventory uses `.example.invalid` placeholders:

- `django-chat-staging`
- `django-chat-production`

Before a real deploy, replace the placeholder `ansible_host`,
`django_chat_wagtail_fqdn`, host rule, and allowed-host values with
Django Chat-specific staging or production values. Do not copy Python
Podcast hostnames, buckets, credentials, routes, or other service details.

Public deployment defaults live in:

- `deploy/group_vars/django_chat.yml`
- `deploy/group_vars/staging.yml`
- `deploy/group_vars/production.yml`

Secrets are loaded from:

- `deploy/secrets/staging.sops.yml`
- `deploy/secrets/production.sops.yml`

Only encrypted SOPS files belong at those paths, and those paths are ignored by
Git. Example shapes are committed as `deploy/secrets/*.example.yml`.

## Static Assets

`just deploy-static-check` runs:

```sh
uv run python manage.py check_django_chat_static_assets
```

That command verifies that the installed `django-cast` and `cast-bootstrap5`
package Vite manifests exist before a deploy starts.

During deployment, `wagtail_deploy` runs `collectstatic` and then fails if these
collected files are missing:

- `staticfiles/staticfiles.json`
- `staticfiles/cast_bootstrap5/vite/manifest.json`
- `staticfiles/cast_bootstrap5/vite/manifest.json.gz`
- `staticfiles/cast/vite/manifest.json`
- `staticfiles/cast/vite/manifest.json.gz`

No frontend build is configured in this slice because the required Vite
manifests are bundled with installed Python packages.

## Production Settings

Deployment uses `config.settings.production`. The role renders a `.env` file
with:

- `DJANGO_SETTINGS_MODULE=config.settings.production`
- `DJANGO_SECRET_KEY`
- `DJANGO_ALLOWED_HOSTS`
- `DATABASE_URL`
- Django Chat S3 media settings
- cache/admin/email values needed by the app and deploy role

The production settings module keeps local/test behavior unchanged and requires
real secret values from the deployment environment.

Security defaults are conservative for an early staging-capable deploy path:
`DJANGO_SECURE_HSTS_SECONDS` defaults to `60` seconds. Before production
cutover, raise HSTS to a production value only after DNS, HTTPS, canonical host,
and rollback decisions are settled.

## Runtime Sizing

The shared deploy vars override the generic `wagtail_deploy` role defaults for
a small VPS:

- `wagtail_gunicorn_workers: 3`
- `wagtail_gunicorn_timeout: 120`
- `uv_version: "0.11.7"`

The transcript database worker remains disabled by default, so this sizing is
for the web app, local PostgreSQL, and Traefik only.

## Transcript Worker

`wagtail_db_worker_enabled` defaults to `false`. The deploy vars keep
`wagtail_db_worker_backend: cast_transcripts` ready for later use, but no worker
unit is installed unless transcript publishing or conversion work explicitly
enables it.

## Out Of Scope

This deployment slice does not include:

- a real staging deploy
- a real production deploy
- host admin account creation
- host review docs
- DNS changes
- feed redirects
- podcast directory updates
- production migration
- transcript conversion
- backup/restore hardening
