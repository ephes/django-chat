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
just deploy-bootstrap-target production # after setting standalone mode
```

Standalone bootstrap requires `django_chat_host_mode: standalone` in the target's
host/group vars. Shared staging rejects bootstrap and standalone mode.
Production remains a placeholder and defaults to shared mode until configured.

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

The deploy play sets Git's `http.version` to `HTTP/1.1` through task-scoped
environment variables. This avoids the staging host's unreliable Git/libcurl
HTTP/2 transport when `uv sync --frozen` fetches django-cast's public
development branch, without changing host-wide Git configuration.

Staging is live at `https://djangochat.staging.django-cast.com`. Re-run
`just deploy-staging` after repo-side deployment changes that need to reach the
host. Do not run production deployment from this slice.

Staging sets `django_chat_cast_comments_enabled: true`, which renders
`CAST_COMMENTS_ENABLED=true` into the deployed app environment. Production
inherits the shared default `false`. With the staging global gate open, the
podcast page's Wagtail `comments_enabled` toggle activates comments across the
imported catalog. Individual episode/post `comments_enabled` toggles remain
available as opt-outs, so reviewers can control comments from the admin without
another deploy or environment change.

Staging also enables `django_chat_cast_voxhelm_known_speaker_enabled`, so
diarized episode jobs send approved host/guest voice references to Voxhelm and
store its per-segment name suggestions for editorial review. Production keeps
that integration opt-in. `django_chat_disable_transcript_cache` is enabled on
staging as well, so corrections in the player transcript panel appear after the
next page load instead of remaining in the browser cache for up to an hour. A
browser that cached the player response before this staging policy was deployed
needs one hard refresh; responses fetched afterward are not stored. Podlove,
DOTe, and WebVTT files served through media storage or a CDN retain their own
cache policies and are unaffected by this middleware.

## Proxy ownership and regression protection

`django_chat_host_mode` defaults to `shared`. In shared mode, deployment requires
an existing executable Traefik binary, dynamic route directory and active
`traefik` service. These read-only checks run before application changes. The
app deploy skips host bootstrap and the full `traefik_deploy` role;
`wagtail_deploy` still writes Django Chat's application route. It does not
replace Traefik's binary, static configuration, service unit or certificate
store. Shared staging is always required to use this mode, even if a caller
tries to override it with extra vars.

For a new, independently owned VPS, explicitly set
`django_chat_host_mode: standalone` in that host's inventory variables. This
opts into baseline host tasks and full proxy installation. Standalone setup
refuses hosts already enrolled in `/var/lib/traefik-transactions`. The pinned
collection independently guards full proxy writes on enrolled hosts.

Before the next staging deploy, rerun `just deploy-bootstrap` to replace the
old installed collection. The previous pin lacked the write guard and could
revert a shared proxy's executable and static settings. Merely setting a newer
Traefik version does not protect static configuration.

Run only the shared-proxy preflight, without app deployment or secrets:

```sh
cd deploy
uvx --from ansible-core ansible-playbook -i inventory/hosts.yml deploy.yml \
  -l staging --tags proxy-preflight
```

Regression tests exercise the real Ansible role conditions with harmless local
fixture roles: shared mode skips full proxy/bootstrap writes even with
`traefik_force_update=true`, explicit standalone setup selects them, and invalid
modes, missing/inactive proxies, or a standalone override on staging fail before
application mutation. `uv sync` installs the declared Ansible dev dependency,
so `just test` runs these regressions without a global Ansible installation;
missing Ansible fails the tests instead of silently skipping them.

October 9, 2026 validation: corrected deployment files and the pinned collection
were installed in staging's existing checkout after backing up the old files.
Shared preflight passed locally and natively on staging with zero changes;
standalone mode on staging and the collection's enrolled-host full-write guard
both refused before mutation. Traefik's binary/static configuration hashes and
process ID remained unchanged; Django Chat's TLS homepage redirected normally
to `/episodes/`, which returned 200.
The application and database were not redeployed during this workflow repair.
`just test` passed (410 tests; 18 optional browser tests skipped), `just
deploy-check`, lint, typecheck and `prek run --all-files` passed. No separate
changelog convention exists; this deployment note records the workflow change.

## Ansible Dependencies

`deploy/requirements.yml` installs:

- `local.ops_library` from `https://github.com/ephes/ops-library.git` pinned to
  commit `e92fb68ceec622d1f0fcdf07c040fba0ad6fb113`
- `community.postgresql` pinned to `4.2.0`
- `community.general` pinned to `12.6.0`
- `community.sops` pinned to `2.3.0`
- `ansible.posix` pinned to `2.1.0`

Dependencies are installed under `deploy/.ansible/`, which is ignored by Git.
Bootstrap uses `--force` so an existing collection with the same advertised
version cannot retain code from an older commit. Standalone Linux amd64 setup
pins Traefik 3.7.14 and the audited archive checksum; other architectures must
explicitly configure their matching release checksum before setup.

## Inventory And Vars

Committed inventory uses the live staging host and a production placeholder:

- `django-chat-staging`: `djangochat.staging.django-cast.com`
- `django-chat-production`: `production.djangochat.example.invalid`

Before any production deploy, replace the production placeholder
`ansible_host`, `django_chat_wagtail_fqdn`, host rule, and allowed-host values
with Django Chat-specific production values. Do not copy Python Podcast
hostnames, buckets, credentials, routes, or other service details.

`deploy/group_vars/staging.yml` carries the live shared staging FQDN
`djangochat.staging.django-cast.com` and opts staging into the global comments
gate, known-speaker transcript suggestions, and uncached transcript review.

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

That command verifies that the installed `django-cast` package Vite manifest
exists before a deploy starts.

During deployment, `wagtail_deploy` runs `collectstatic` and then fails if these
collected files are missing:

- `staticfiles/staticfiles.json`
- `staticfiles/cast/vite/manifest.json`
- `staticfiles/cast/vite/manifest.json.gz`

No frontend build is configured in this slice because the required Vite
manifests are bundled with installed Python packages. First-party Django Chat
CSS is minified inside Django's staticfiles storage during `collectstatic`:
`django_chat.core.staticfiles.MinifiedCompressedManifestStaticFilesStorage`
re-minifies `django_chat/css/*.css` into `STATIC_ROOT` before Django's
manifest hashing rewrites URLs and before WhiteNoise writes compressed
variants. Minification always restarts from the pristine finder source (not
the previously collected, already-minified copy), so minifier changes take
effect on the next deploy even when the CSS source itself is unchanged.
Source CSS remains readable in the repository, and no Node/npm toolchain is
required on the deployment host.

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
(CloudFront), and episode detail pages render the django-cast custom audio
player backed by those URLs. The sample command still supports fixture-backed smoke
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

When S3 media storage is enabled, Django Chat also configures
`STORAGES["cast_public_transcripts"]` to the same S3 bucket and media host as
`STORAGES["default"]`. django-cast uses that alias for public Podlove JSON,
WebVTT, and DOTe transcript artifacts, while private sidecars and voice-reference
clips use `STORAGES["cast_voice_references"]` with the same durable bucket and
object keys but without the public media host. This replaces the temporary
`cast_private_media` public-S3 compatibility workaround.

Before bumping or migrating django-cast transcript storage, back up the current
public transcript artifact prefix and the private known-speaker artifact
prefixes:

```sh
aws s3 sync "s3://$DJANGO_CHAT_S3_STORAGE_BUCKET_NAME/cast_transcript/" \
  "./backups/cast_transcript-$(date +%Y%m%d%H%M%S)/"
aws s3 sync "s3://$DJANGO_CHAT_S3_STORAGE_BUCKET_NAME/cast_transcript_speakers/" \
  "./backups/cast_transcript_speakers-$(date +%Y%m%d%H%M%S)/"
aws s3 sync "s3://$DJANGO_CHAT_S3_STORAGE_BUCKET_NAME/cast_voice_references/" \
  "./backups/cast_voice_references-$(date +%Y%m%d%H%M%S)/"
```

The singular `cast_transcript/` S3 prefix is the django-cast upload prefix for
the public `Transcript.podlove`, `Transcript.vtt`, and `Transcript.dote`
artifact fields. It is unrelated to the plural `cast_transcripts` task backend
name used by the transcript worker. `cast_transcript_speakers/` stores private
known-speaker suggestion sidecars and `cast_voice_references/` stores private
voice-reference clips. For S3-compatible providers, use the provider's
equivalent endpoint/profile flags.

Django Chat was bumped from django-cast `173a3314`, which did not include
django-cast migrations `0077_private_transcript_artifact_storage` or
`0078_private_voice_reference_storage`. Tracked environments upgrading from
that pin will therefore run the patched no-op `0077` and the private artifact
`0078` migration from django-cast `0.2.65` at `a1db64f0` for the first time.
Django Chat's
`cast_voice_references` alias points at the same bucket/keyspace as default
media, so `0078` sees existing `cast_transcript_speakers/` and
`cast_voice_references/` objects in place instead of copying them to local
private storage and deleting S3 originals. If an environment was manually
pointed at an intermediate django-cast revision, check the `django_migrations`
table for `cast` migrations `0077` and `0078` before deploying this bump and
confirm transcript artifacts still exist under `cast_transcript/`,
`cast_transcript_speakers/`, and `cast_voice_references/`.

The Wagtail 8 dependency upgrade also applies django-cast migrations `0079`
through `0082`. These
add the podcast iTunes type, convert django-cast's retired built-in heading
blocks to rich-text headings, remove that block, and make theme choices safe
under Wagtail 8. Django Chat's `show_note_heading` is a separate custom block
and is not targeted by the built-in heading conversion.

To restore that backup, reverse the sync source and destination:

```sh
aws s3 sync "./backups/cast_transcript-YYYYMMDDHHMMSS/" \
  "s3://$DJANGO_CHAT_S3_STORAGE_BUCKET_NAME/cast_transcript/"
aws s3 sync "./backups/cast_transcript_speakers-YYYYMMDDHHMMSS/" \
  "s3://$DJANGO_CHAT_S3_STORAGE_BUCKET_NAME/cast_transcript_speakers/"
aws s3 sync "./backups/cast_voice_references-YYYYMMDDHHMMSS/" \
  "s3://$DJANGO_CHAT_S3_STORAGE_BUCKET_NAME/cast_voice_references/"
```

After `migrate`, verify at least one existing transcript page and the matching
player transcript API still return transcript cues before deleting the backup.
The configured `cast_public_transcripts` alias uses the same public media host,
so existing `cast_transcript/` object keys and generated transcript URLs should
remain stable. Verify known-speaker review still opens existing speaker
sidecars and voice-reference clips in the Wagtail admin before deleting private
artifact backups.

Security defaults are conservative for an early staging-capable deploy path:
`DJANGO_SECURE_HSTS_SECONDS` defaults to `60` seconds. Before production
cutover, raise HSTS to a production value only after DNS, HTTPS, canonical host,
and rollback decisions are settled.

## Runtime Sizing

The shared deploy vars override the generic `wagtail_deploy` role defaults for
a small VPS:

- `wagtail_gunicorn_workers: 3`
- `wagtail_gunicorn_timeout: 120`
- `uv_version: "0.12.19"`

Staging overrides `uv_version` to `"latest"`: the staging host is shared and
ops-control keeps its `/usr/local/bin/uv` on the latest release, so a pinned
older version would downgrade that shared binary on every deploy.

The `cast_transcripts` database worker is enabled for all environments so
Wagtail's Generate transcript action can queue Voxhelm completion work outside
the web request. Web sizing remains intentionally small.

The shared deploy vars also set `wagtail_traefik_cert_resolver: "letsencrypt"`
so the generated Traefik route requests a real ACME certificate instead of
falling back to Traefik's default self-signed certificate.

## Transcript Worker

The shared group vars enable the django-tasks database worker for all
environments:

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
Voxhelm transcription also requires the host running Django/Wagtail and
`django-chat-db-worker.service` to reach the Tailscale network where the
Voxhelm API is exposed; browser access to Wagtail admin is not enough.

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
