# Deployment

Django Chat deploys through the private ops-control repository, like the other
Wagtail sites (homepage, python-podcast): its pyinfra `django_chat` site
(`pyinfra_support/django_sites.py`) deploys to the shared staging host and
replaced the former Ansible playbook `playbooks/deploy-django-chat.yml`. Settings,
hostnames and the encrypted secret live in ops-control (see its
`docs/DJANGO_CHAT.md`). This repository no longer carries Ansible; the former
self-contained `deploy/` directory (with an ops-library pinned to 2.31.15) was
retired in October 2026 so that there is a single deploy path.

## Commands

Deploy staging from this checkout:

```sh
just deploy-staging
```

The recipe runs `deploy-static-check`, then `just deploy-one django-chat
staging` in the ops-control checkout named by `OPS_CONTROL_DIR` (default:
`../ops-control`, next to this repository) with `PROJECTS_ROOT` set to this
checkout's parent directory, because ops-control rsyncs
`$PROJECTS_ROOT/django-chat`. The checkout therefore has to be named
`django-chat`. ops-control maps `django-chat` to its pyinfra `django_chat`
service. Running the ops-control recipe directly is equivalent:

```sh
cd ../ops-control
PROJECTS_ROOT="$(cd .. && pwd)" just deploy-one django-chat staging
```

The deploy rsyncs the working tree as it is, including uncommitted changes.

There is no production deployment. Production is a placeholder in ops-control,
whose `django_chat` site refuses every host but `staging`.

Staging is live at `https://djangochat.staging.django-cast.com`. Re-run
`just deploy-staging` after repo-side changes that need to reach the host.

The deploy holds Git to HTTP/1.1 through environment variables for
`uv sync` only (`uv_env` of the `django_chat` site). This avoids the staging
host's unreliable Git/libcurl HTTP/2 transport when `uv sync --frozen` fetches
django-cast's public development branch, without changing host-wide Git
configuration. It also runs `manage.py ensure_default_site`, so Wagtail's
default Site carries the deployed hostname. The app and the transcript worker
restart whenever the source, the dependencies or the rendered environment
change; `just pyinfra-check django_chat staging` in ops-control lists what a
deploy would change.

Staging enables Django Chat's global comments gate (`CAST_COMMENTS_ENABLED=true`
in the deployed environment; the ops-control default is off). With the staging
global gate open, the podcast page's Wagtail `comments_enabled` toggle
activates comments across the imported catalog. Individual episode/post
`comments_enabled` toggles remain available as opt-outs, so reviewers can
control comments from the admin without another deploy or environment change.

Staging also enables Voxhelm known-speaker suggestions
(`CAST_VOXHELM_KNOWN_SPEAKER_ENABLED=true`), so diarized episode jobs send
approved host/guest voice references to Voxhelm and store its per-segment name
suggestions for editorial review, and disables the transcript response cache
(`DJANGO_CHAT_DISABLE_TRANSCRIPT_CACHE=true`), so corrections in the player
transcript panel appear after the next page load instead of remaining in the
browser cache for up to an hour. A browser that cached the player response
before this staging policy was deployed needs one hard refresh; responses
fetched afterward are not stored. Podlove, DOTe, and WebVTT files served
through media storage or a CDN retain their own cache policies and are
unaffected by this middleware. The three flags are set in ops-control's
`inventories/prod/host_vars/staging.yml`.

## Proxy

The staging host's Traefik belongs to ops-control. The `django_chat` deploy
writes only Django Chat's dynamic route (`/etc/traefik/dynamic/django-chat.traefik.yml`,
`Host(\`djangochat.staging.django-cast.com\`)`, certificate resolver
`letsencrypt`); it never installs or reconfigures Traefik itself. The former
standalone/clean-VPS mode of the repo-local deploy is gone with it.

## Secrets

The staging secret lives in ops-control at `secrets/staging/django-chat.yml`,
encrypted to ops-control's age recipients. Edit it there with `sops` and commit
it in ops-control. `just dev` and `just manage-staging-media` read the same
file (`DJANGO_CHAT_STAGING_SECRET_FILE`, default
`$OPS_CONTROL_DIR/secrets/staging/django-chat.yml`).

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

During deployment, ops-control runs `collectstatic` and then fails if these
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
setting, extend ops-control's `django_chat` site before relying on it.

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

### Wagtail 8.1 and django-cast e0c632ad (2026-11-18)

`uv.lock` moves Wagtail from 8.0.1 to 8.1 (`pyproject.toml` allows
`>=8.1,<8.2`), django-cast develop from `b594f805` to `e0c632ad` (release
0.2.68 plus the 0.2.69 version bump), draftjs-exporter from 7.1.0 to 7.3.1
(Wagtail 8.1 requires `>=7.3.0,<8.0`) and soupsieve from 3.0.2 to 4.1.1
(django-cast's security floor). The numbered Wagtail migrations are identical
in 8.0.1 and 8.1. django-cast adds four migrations, all additive:

- `cast.0091_spamfilter_retrain_attempt`: nullable UUID column.
- `cast.0092_transcript_upload_help`: help texts only, no SQL.
- `cast.0093_podcast_contributor_order`: `contributor_order` column, filled
  with `guests_first` and then without a database default.
- `cast.0094_previous_transcript_version`: nullable file column. New files go
  to the private `cast_voice_references` storage under
  `cast_transcript_versions/`.

Wagtail 8.1 changes checked for this site: there is no `wagtail_hooks.py`, no
use of the removed admin API (`/admin/api/main/`, `construct_admin_api`), no
`ajax_template`, no sitemap and no `WAGTAIL_I18N_ENABLED`. Redirects are now
only created automatically for live pages; the default is kept. On Django 6.1
Wagtail sends admin mail through `mailers.default`, which Django derives from
`EMAIL_BACKEND` while `MAILERS` is unset.

django-cast upgrade actions checked for this site:

- Author comment edits must send the comment's revision token, or the edit is
  refused with HTTP 409. `templates/comments/comment.html` overrides
  django-cast's template, so it now renders `data-revision` like the upstream
  template. No other overridden template changed upstream.
- The configured `cast_public_transcripts` and `cast_voice_references` storages
  now fail loudly instead of falling back.
- The theme is registered through `CAST_CUSTOM_THEMES`, and there are no
  `confirm_delete.html` overrides and no custom Audio/Video chooser code.
- Cached audio sizes are now bound to the file name. Sizes cached before the
  upgrade have no file name, so every uncached feed render asks storage for
  each enclosure size, and a single storage error fails the feed. The importer
  now records the file name with the copied byte size. After deploying, bind
  the existing sizes once (sizes are read from storage; safe to re-run):

  ```sh
  .venv/bin/python manage.py cache_django_chat_audio_sizes          # dry-run
  .venv/bin/python manage.py cache_django_chat_audio_sizes --write
  ```
- Collected static files: after the deploy, compare each static file that
  Django's staticfiles finders select from django-cast and the installed
  Wagtail apps with its collected copy (for example
  `fluent_comments/js/ajaxcomments.js`, which sends the comment revision
  token). Files of Wagtail apps this site does not install are not collected.
  The deploy's plain `collectstatic` skips a source that is not newer than the
  collected copy, and the venv hardlinks files from the uv cache with the
  cache's timestamps. If a file differs, rebuild the static directory with the
  upgraded commit: under the shared deploy lock stop both units, empty
  `/home/django-chat/site/staticfiles` as the `django-chat` user and run the
  same `just deploy-one` again. No database step is involved.

Local checks: `just check` (639 tests), `just test-browser` (18), `just
docs-check` and `makemigrations --check`. In a rehearsal on PostgreSQL 17, a
database migrated and filled with synthetic content and the bundled sample
import under the old lock planned and applied only `cast.0091` to `cast.0094`
under the new one, and pages, feeds and the episode list returned the same
responses before and after.

Rollback: hold the shared deploy lock on the host for the whole sequence
(`python -m pyinfra_support.deploy_lock acquire staging` in ops-control,
export `OPS_CONTROL_DEPLOY_LOCK=staging=<token>` so the nested `just
deploy-one` accepts it, release afterwards):

1. As root stop `django-chat.service` and `django-chat-db-worker.service`,
   so no request or task reads the columns while they are dropped.
2. As the `django-chat` user, with the new code still installed, run
   `manage.py migrate cast 0090`. A rollback without this step leaves
   `contributor_order` without a database default, and the old code cannot
   create podcasts. Unapplying the migrations drops the new columns: the spam
   filter retrain attempt, each podcast's contributor order and the links to
   previous transcript versions. The private files stay in storage.
3. As the `django-chat` user empty `/home/django-chat/site/staticfiles` (what
   `collectstatic --clear` does; it only holds collected files), so the old
   packages' static files are collected again instead of being skipped as
   older.
4. In ops-control run `just deploy-one django_chat staging` with
   `PROJECTS_ROOT` set to a directory whose `django-chat` subdirectory is a
   clean checkout of the previous commit. It installs the old lock, collects
   the static files into the empty directory and starts both units. Check each
   unit with its own `systemctl is-active`.

The bound size entries stay in the audio data; the old django-cast ignores
them. In the rehearsal, the old code served the same responses and the same
`showmigrations` after step 2 as before the upgrade.

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

## Application Python

ops-control pins the uv-managed interpreter for the application venv to
3.15.2 in its pyinfra `django_chat` site (`app.python` with
`assert_python_version` in `pyinfra_support/django_sites.py`; 3.14.4 before
October 2026). The rsynced `.python-version` must name the same version:
`uv sync --frozen` honours it and would otherwise replace the venv with that
interpreter. A test here keeps `.python-version` at 3.15.2.
Use uv 0.13.6 or newer for the 3.15.2 interpreter download. This configuration
update does not itself deploy the runtime to staging. To roll back, align the
source requirement, source pin, and deployment configuration before redeploying.

## Runtime Sizing

ops-control's `django_chat` site is sized for a small VPS: 3 gunicorn workers
with a 120 second timeout on 127.0.0.1:10015, and the Django admin under
`django-admin/`. uv is ops-control's pinned release, the same binary every
ops-control deploy to that host uses.

The `cast_transcripts` database worker is enabled so Wagtail's Generate
transcript action can queue Voxhelm completion work outside the web request.
Web sizing remains intentionally small.

## Transcript Worker

ops-control enables the django-tasks database worker for the
`cast_transcripts` backend.

The deployed unit is `django-chat-db-worker.service` and runs
`manage.py db_worker --backend cast_transcripts --interval 5`.

Voxhelm-backed transcript generation uses django-cast's `CAST_VOXHELM_*`
settings. For staging, keep the Voxhelm API base URL, producer token, model,
and language in the staging secret (ops-control
`secrets/staging/django-chat.yml`) as
`cast_voxhelm_api_base`, `cast_voxhelm_api_key`, `cast_voxhelm_model`, and
`cast_voxhelm_language`; ops-control renders them into the
deployed `.env`. The matching producer token must also be present in the
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
- backups: the staging database has no backup target yet (ops-control's
  `docs/DJANGO_CHAT.md`)
