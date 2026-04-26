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
They do not require `ops-control`. The full deploy playbook explicitly restarts
the Django Chat app service after every `wagtail_deploy` run. This makes
deploy re-runs include a brief app restart, but it ensures updated
dependencies, Gunicorn, and collected static assets are picked up by the live
process.

Staging is live at `https://djangochat.staging.django-cast.com`. Re-run
`just deploy-staging` after repo-side deployment changes that need to reach the
host. Do not run production deployment from this slice.

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

Committed inventory uses the live staging host and a production placeholder:

- `django-chat-staging`: `djangochat.staging.django-cast.com`
- `django-chat-production`: `.example.invalid`

Before any production deploy, replace the production placeholder
`ansible_host`, `django_chat_wagtail_fqdn`, host rule, and allowed-host values
with Django Chat-specific production values. Do not copy Python Podcast
hostnames, buckets, credentials, routes, or other service details.

`deploy/group_vars/staging.yml` carries the live shared staging FQDN
`djangochat.staging.django-cast.com`.

`ansible_python_interpreter` is pinned to `/usr/bin/python3` for deployed
hosts so Ansible's PostgreSQL modules use the system Python with distro
PostgreSQL bindings. Confirm that path exists on any future production host
before replacing the production placeholder.

Public deployment defaults live in:

- `deploy/group_vars/django_chat.yml`
- `deploy/group_vars/staging.yml`
- `deploy/group_vars/production.yml`

Secrets are loaded from:

- `deploy/secrets/staging.sops.yml`
- `deploy/secrets/production.sops.yml`

Only encrypted SOPS files belong at those paths, and those paths are ignored by
Git. Example shapes are committed as `deploy/secrets/*.example.yml`.

For the shared staging environment, only operators managing that staging deploy
should be SOPS recipients. Host reviewers do not need SOPS decrypt access just
to use the repo or Wagtail admin.

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

The deployed application also needs `gunicorn` available in the app virtualenv,
because the generated systemd unit starts `{{ wagtail_venv_bin }}/gunicorn`,
and `psycopg[binary]` so production settings can connect to the PostgreSQL
database from the app virtualenv.

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

The current staging secret shape includes:

- `django_aws_access_key_id`
- `django_aws_secret_access_key`
- `django_aws_storage_bucket_name`
- `cloudfront_domain`

Those values back Django Chat media storage during deployment. For the current
deploy path, a Django Chat-specific S3-compatible bucket is required if staging
should self-host copied audio and other media. Metadata-only browsing can work
without copied audio, but that is not a complete playback proof. If you choose
a non-AWS S3-compatible provider that needs an explicit endpoint or region
setting, extend the deploy vars before the first live deploy.

Current staging media status: sample audio copy is blocked. Running
`import_django_chat_sample --copy-audio` on the deployed staging app fails on
S3 object access before the first MP3 is saved. Diagnostics confirmed the app
IAM user is not allowed to perform `s3:PutObject` on the staging media bucket,
and `HeadBucket` / `HeadObject` also return `403 Forbidden`. Fix the staging
media credential or bucket policy, then re-run the deployed command and verify
a copied media URL through the public media host.

The app media principal needs, at minimum:

- bucket-level `s3:ListBucket` and `s3:GetBucketLocation` on the media bucket
- object-level `s3:GetObject`, `s3:PutObject`, and `s3:DeleteObject` on the
  media bucket contents

`s3:GetObject` and `s3:ListBucket` are needed for django-storages existence
checks and idempotent import verification, not only for browser delivery.
Public media delivery through CloudFront or another media host may require
separate bucket policy or origin-access configuration.

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

The shared deploy vars also set `wagtail_traefik_cert_resolver: "letsencrypt"`
so the generated Traefik route requests a real ACME certificate instead of
falling back to Traefik's default self-signed certificate.

## Transcript Worker

`wagtail_db_worker_enabled` defaults to `false`. The deploy vars keep
`wagtail_db_worker_backend: cast_transcripts` ready for later use, but no worker
unit is installed unless transcript publishing or conversion work explicitly
enables it.

## Staging Admin Bootstrap

Create or refresh Wagtail host-review accounts on the deployed staging app,
not in local development databases. Use production settings explicitly when
running management commands on the host:

```sh
cd /home/django-chat/site
DJANGO_SETTINGS_MODULE=config.settings.production .venv/bin/python manage.py ...
```

Do not store human Wagtail admin passwords in this repository or in
repo-managed SOPS files. For the first staging review, the
`host-review-admin` superuser was created with a generated temporary password
stored only in a mode-600 bootstrap handoff file on the staging host. Retrieve
and share that credential through the agreed secure channel, then rotate it in
Wagtail admin or replace the account when host review access is settled.

## Out Of Scope

The deployment scaffold and host review docs are in this repository, and live
staging is available for host review. This deployment path does not include:

- a real production deploy
- DNS changes
- feed redirects
- podcast directory updates
- production migration
- transcript conversion
- backup/restore hardening
