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

Current staging media status: full-catalog audio copy has been verified.
`import_django_chat_catalog --copy-cover-image --copy-audio` on the deployed
staging app copied audio for all live imported episodes under the `episodes`
podcast; copied media URLs are served through the configured public media host
(CloudFront), and episode detail pages render the django-cast Podlove player
backed by those URLs. The sample command still supports fixture-backed smoke
checks, but representative host review should use the catalog command and
audio completeness checks below.

The full-catalog operator path is now:

```sh
cd /home/django-chat/site
DJANGO_SETTINGS_MODULE=config.settings.production \
  .venv/bin/python manage.py import_django_chat_catalog
DJANGO_SETTINGS_MODULE=config.settings.production \
  .venv/bin/python manage.py import_django_chat_catalog --copy-cover-image
DJANGO_SETTINGS_MODULE=config.settings.production \
  .venv/bin/python manage.py measure_django_chat_catalog --host=djangochat.staging.django-cast.com
```

For a safe staging exercise before the full run, add `--max-episodes 3`.
For a rollback-only plan, use `--dry-run --max-episodes 3`. The command
re-fetches RSS and Simplecast metadata on every run, updates existing rows in
place, and skips existing copied audio when the recorded source URL still
matches a stored file.

Full-catalog audio copy is deliberately separate:

```sh
cd /home/django-chat/site
DJANGO_SETTINGS_MODULE=config.settings.production \
  .venv/bin/python manage.py import_django_chat_catalog --copy-cover-image --copy-audio
```

The research PRD observed about 11 GB of RSS-reported audio. Do not run
`--copy-audio` casually; it performs real network transfer and writes media to
the configured bucket. The catalog path streams audio through a temporary file
and Django storage, so it does not read full MP3s into process memory.

The app media principal needs, at minimum:

- bucket-level `s3:ListBucket` and `s3:GetBucketLocation` on the media bucket
- object-level `s3:GetObject`, `s3:PutObject`, and `s3:DeleteObject` on the
  media bucket contents

`s3:GetObject` and `s3:ListBucket` are needed for django-storages existence
checks and idempotent import verification, not only for browser delivery.
Public media delivery through CloudFront or another media host may require
separate bucket policy or origin-access configuration. Make sure the bucket
ARN in the policy matches the value of `django_aws_storage_bucket_name`
exactly; an ARN that names a different bucket will silently deny every
request from the app principal.

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

The `cast_transcripts` database worker is enabled for staging so Wagtail's
Generate transcript action can queue Voxhelm completion work outside the web
request. Web sizing remains intentionally small.

The shared deploy vars also set `wagtail_traefik_cert_resolver: "letsencrypt"`
so the generated Traefik route requests a real ACME certificate instead of
falling back to Traefik's default self-signed certificate.

## Transcript Worker

Staging enables the django-tasks database worker for transcript generation:

```yaml
wagtail_db_worker_enabled: true
wagtail_db_worker_backend: cast_transcripts
```

The deployed unit is `django-chat-db-worker.service` and runs
`manage.py db_worker --backend cast_transcripts --interval 5`.

Voxhelm-backed transcript generation uses django-cast's `CAST_VOXHELM_*`
settings. For staging, keep the Voxhelm API base URL, producer token, model,
and language in `deploy/secrets/staging.sops.yml` as
`cast_voxhelm_api_base`, `cast_voxhelm_api_key`, `cast_voxhelm_model`, and
`cast_voxhelm_language`; `deploy/group_vars/django_chat.yml` renders them into
the deployed `.env`. The matching producer token must also be present in the
Voxhelm deployment secrets and rendered into `VOXHELM_BEARER_TOKENS`.

To create a transcript from Wagtail admin:

1. Sign in at `https://djangochat.staging.django-cast.com/cms/`.
2. Open **Pages**, then edit the podcast episode that should receive a
   transcript.
3. Use the page action button labeled **Generate transcript**.
4. Wait for `django-chat-db-worker.service` to process the queued
   `cast_transcripts` task.
5. Re-open the public episode page and confirm it links to
   `/episodes/<slug>/transcript/`.

The action is only visible for users who can edit the episode and change the
attached podcast audio object. The episode must have copied `podcast_audio`
with an absolute HTTP(S) media URL that Voxhelm is allowed to fetch.

Check worker status with:

```sh
systemctl is-active django-chat-db-worker.service
journalctl -u django-chat-db-worker.service --since "10 minutes ago" --no-pager
```

For a synchronous operator fallback, run the django-cast management command on
the staging host:

```sh
cd /home/django-chat/site
sudo -u django-chat env DJANGO_SETTINGS_MODULE=config.settings.production \
  .venv/bin/python manage.py generate_transcripts --episode-id <episode-id>
```

Look up episode ids with:

```sh
cd /home/django-chat/site
sudo -u django-chat env DJANGO_SETTINGS_MODULE=config.settings.production \
  .venv/bin/python manage.py shell -c '
from cast.models import Episode, Podcast
podcast = Podcast.objects.get(slug="episodes")
for episode in Episode.objects.live().descendant_of(podcast).order_by("-visible_date")[:20]:
    print(episode.id, episode.slug, episode.title)
'
```

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
staging is available for review preparation. Full host review should still wait
for the latest `docs/implementation-status.md` next-action guidance, especially
any pre-handoff performance decision recorded there.
This deployment path does not include:

- a real production deploy
- DNS changes
- feed redirects
- podcast directory updates
- production migration
- transcript conversion
- backup/restore hardening
