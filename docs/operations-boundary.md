# Operations Boundary

Django Chat is deployed by the private ops-control repository, which holds the
inventory, the staging hostname and settings, the encrypted secret and the
playbook (`playbooks/deploy-django-chat.yml`, current ops-library roles). This
repository holds the application and a `just deploy-staging` shortcut that
calls ops-control. There is no second, repo-local deploy path: the former
`deploy/` directory was retired in October 2026.

## What Lives In This Repo

- the application, its `uv.lock` and `.python-version` (the deploy rsyncs the
  checkout; ops-control refuses a `.python-version` other than its pin)
- `just deploy-staging` and `just deploy-static-check`
- the deployment and host-review documentation

## What Lives In ops-control

- `playbooks/deploy-django-chat.yml` and the `just deploy-one django-chat`
  dispatch
- the staging host values in `inventories/prod/host_vars/staging.yml`
- the SOPS/age-encrypted staging secret `secrets/staging/django-chat.yml`
- `docs/DJANGO_CHAT.md`

## What Stays Off Repo

- decrypted SOPS files
- age private keys
- real Django secret keys
- database passwords
- S3/object-storage credentials
- Sentry DSNs
- Mailgun keys
- admin passwords
- staging bootstrap password handoff files
- unrelated infrastructure inventory
- private operator notes

Edit the staging secret in ops-control and commit it there:

```sh
sops ../ops-control/secrets/staging/django-chat.yml
```

For the shared staging environment, only operators managing that staging
deployment are SOPS recipients (ops-control's `.sops.yaml`). Host
reviewers do not need SOPS decrypt access just to review the site or log into
Wagtail admin.

## Operator Workstation

Required local tools:

- `uv`
- `just`
- `sops` and `yq` (for `just dev` / `just manage-staging-media`)
- an ops-control checkout next to this one (or `OPS_CONTROL_DIR`), with its
  Ansible tooling and the ops-library collection installed
  (`just install-local-library` in ops-control)
- the age private key that decrypts ops-control's secrets
  (`SOPS_AGE_KEY_FILE`, default `~/.config/sops/age/keys.txt`)
- root SSH access to the staging host

## Media

The staging secret carries the media credentials and host values used by the
deployment:

- `django_aws_access_key_id`
- `django_aws_secret_access_key`
- `django_aws_storage_bucket_name`
- `cloudfront_domain`

When S3 media storage is enabled, Django Chat maps django-cast's
`cast_public_transcripts` storage alias to the same public media bucket/media
host. That alias is for public Podlove JSON, WebVTT, and DOTe transcript
artifacts. Django Chat also maps `cast_voice_references` to the same durable
bucket/keyspace without the public media host and with signed private defaults,
so django-cast private sidecars and voice-reference clips do not fall back to
local disk during storage migrations.

## Command Boundary

`just deploy-static-check` checks the bundled django-cast Vite manifest
locally; it contacts no host.

`just deploy-staging` runs that check and then `just deploy-one django-chat
staging` in ops-control. The ops-control play loads the staging secret, syncs
this checkout, provisions PostgreSQL, installs Python through uv, renders
`.env`, runs migrations and collectstatic, checks required static files,
updates the Wagtail search index, installs the systemd units, writes the
Traefik route and runs `ensure_default_site`. It never installs or
reconfigures Traefik itself. Production is not set up; ops-control refuses
every host but staging.

Host review docs now exist in this repository, and live staging is deployed at
`https://djangochat.staging.django-cast.com`. Host admin account creation and
catalog import happen on the deployed staging app with production settings.
HTTPS, static assets, full-catalog content, Wagtail admin access, copied
full-catalog audio served through the public media host, and a Voxhelm-backed
transcript demo have all been verified end-to-end for review preparation. The
live full-catalog import command is part of the app repo and should be run from
the deployed environment when staging is being refreshed for representative
review:

```sh
DJANGO_SETTINGS_MODULE=config.settings.production \
  .venv/bin/python manage.py import_django_chat_catalog --copy-cover-image
```

Optional full-catalog audio copy uses the same deployed environment with
`--copy-audio`; it can transfer about 11 GB and should be treated as an
operator-approved media operation, not a casual smoke command. Full host review
should wait until the full-catalog media state is coherent and the current
pre-handoff checks listed in `docs/implementation-status.md` are settled.

This repository still does not change DNS, configure Simplecast redirects, cut
over podcast feeds, deploy production, or migrate production.
