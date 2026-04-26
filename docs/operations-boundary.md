# Operations Boundary

Django Chat deployment is self-contained in this repository. Operators should
not need `ops-control` or a manual `ops-library` checkout to inspect or run the
Django Chat deploy path.

## What Lives In This Repo

- `deploy/ansible.cfg`
- `deploy/requirements.yml`
- `deploy/inventory/hosts.yml`
- `deploy/group_vars/`
- `deploy/bootstrap.yml`
- `deploy/deploy.yml`
- `deploy/tasks/bootstrap-host.yml`
- `deploy/secrets/*.example.yml`
- `.sops.yaml`

The committed inventory and group vars contain the live staging host plus
non-secret Django Chat defaults. Production still uses `.example.invalid`
addresses until an operator replaces them with real Django Chat-specific
values. The shared staging FQDN is
`djangochat.staging.django-cast.com`.

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

Real environment secrets belong in SOPS/age-encrypted files at:

```sh
deploy/secrets/staging.sops.yml
deploy/secrets/production.sops.yml
```

Those paths are ignored by Git. The repository only commits example files with
`CHANGEME` values. Keep real ciphertext out of Git history in this shareable
repo so environment-specific secret blobs and old encrypted revisions do not
accumulate for every collaborator.

## Operator Workstation

Required local tools:

- `uv`
- `just`
- `sops`
- `age`
- SSH access to the target VPS

Ansible is executed through `uvx` by default:

```sh
uvx --from ansible-core ansible-galaxy
uvx --from ansible-core ansible-playbook
```

Override `ANSIBLE_GALAXY_CMD` or `ANSIBLE_PLAYBOOK_CMD` only when the operator
has a deliberate alternate Ansible launcher.

Set `SOPS_AGE_KEY_FILE` to the age private key file that can decrypt the target
environment's SOPS file:

```sh
export SOPS_AGE_KEY_FILE="$HOME/.config/sops/age/keys.txt"
```

Back up the age private key outside this repo. Losing the only private key makes
the encrypted deployment secrets unrecoverable.

## Secret Setup

Before creating real encrypted files, replace the empty `.sops.yaml` recipient
configuration with the intended age public recipient or recipients. The file is
committed with `creation_rules: []` because this slice does not know the real
recipient and must not invent one. For the shared staging environment, use only
the age recipients for operators who manage that staging deployment. Host
reviewers do not need SOPS decrypt access just to review the site or log into
Wagtail admin.

Create secrets from the examples:

```sh
cp deploy/secrets/staging.example.yml /tmp/django-chat-staging.yml
sops --encrypt --input-type yaml --output-type yaml \
  /tmp/django-chat-staging.yml > deploy/secrets/staging.sops.yml
rm /tmp/django-chat-staging.yml
```

Edit encrypted secrets with:

```sh
sops deploy/secrets/staging.sops.yml
```

Never commit decrypted temporary files. Prefer a dedicated Django Chat staging
age key that can be rotated or retired independently of unrelated environments.

## Target VPS

The deploy path targets a clean Debian-family VPS, with Ubuntu 24.04 LTS as the
first expected target. The target needs:

- root or sudo SSH access
- DNS for the configured staging or production FQDN already pointing at the VPS
- inbound SSH, HTTP, and HTTPS reachable
- a Django Chat-specific S3-compatible media bucket and credentials
- a real public media host, such as CloudFront or an object-storage public host

The staging secret file carries the media credentials and host values used by
deployment:

- `django_aws_access_key_id`
- `django_aws_secret_access_key`
- `django_aws_storage_bucket_name`
- `cloudfront_domain`

The current deploy vars wire those values into the production environment. If
you choose a non-AWS S3-compatible provider that also needs an explicit
endpoint URL or region override, extend the deploy vars before the first live
deploy.

The deploy playbook validates the local source checkout and encrypted secret
file before gathering remote facts or changing the target host.

## Clean-VPS Bootstrap

`deploy/deploy.yml` runs baseline host tasks before deploying the app:

- assert a Debian-family target
- refresh apt metadata
- install minimal packages needed by deployment
- optionally preserve SSH and enable UFW when explicitly configured
- optionally create and enable swap when explicitly configured

After the baseline tasks, roles run in this order:

1. `local.ops_library.uv_install`
2. `local.ops_library.traefik_deploy`
3. `local.ops_library.wagtail_deploy`

`wagtail_deploy` provisions PostgreSQL, syncs the app, installs Python through
uv, renders `.env`, runs migrations and collectstatic, checks required static
files, updates the Wagtail search index, installs systemd units, and writes
Traefik dynamic config.

## Command Boundary

`just deploy-bootstrap` installs repo-local Ansible dependencies under
`deploy/.ansible/`. It does not contact deployment hosts and does not load
secrets.

`just deploy-bootstrap-target <group>` runs `deploy/bootstrap.yml` for one
inventory group, such as `staging` or `production`. It runs only the clean-VPS
baseline tasks and does not sync app code, load SOPS secrets, run migrations,
collect static files, or touch Traefik/Wagtail roles. Valid target groups are
`staging`, `production`, and `django_chat`.

`just deploy-check` runs the local static asset check, bootstraps Ansible
dependencies, and performs Ansible syntax checks only. It does not deploy.

The full deploy playbook reuses the same clean-VPS baseline task file that
`deploy/bootstrap.yml` exposes for standalone baseline runs.

`just deploy-staging` and `just deploy-production` run the full deployment
playbook for their inventory group. They require real host inventory values,
SOPS secrets, age private key access, and DNS/SSH readiness.

Host review docs now exist in this repository, and live staging is deployed at
`https://djangochat.staging.django-cast.com`. Host admin account creation and
sample import happen on the deployed staging app with production settings.
HTTPS, static assets, sample content, Wagtail admin access, and copied sample
audio served through the public media host have all been verified end-to-end.

This repository still does not change DNS, configure Simplecast redirects, cut
over podcast feeds, deploy production, or migrate production.
