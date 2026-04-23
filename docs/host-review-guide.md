# Host Review Guide

This guide defines the Django Chat staging review workflow for hosts.

## Current Staging Status

No live staging deployment has been attempted from this repository yet. As of
2026-04-22, the repo still contains placeholder staging inventory and no real
SOPS/age recipient or encrypted staging secret file. The live deployment,
sample import on the VPS, and host admin account creation are blocked until an
operator provides real Django Chat-specific staging details.

Do not replace the placeholders below with guessed values. Use only the real
staging FQDN, media host, secret material, and account list approved for Django
Chat.

## Review URLs

These URLs become active only after `just deploy-bootstrap-target staging` and
`just deploy-staging` have completed successfully against the real staging VPS.

- Site: `https://<staging-fqdn>/`
- Episode index: `https://<staging-fqdn>/episodes/`
- Episode detail: `https://<staging-fqdn>/episodes/<slug>/`
- Wagtail admin: `https://<staging-fqdn>/cms/`

The repository uses `/cms/` for Wagtail admin. Django's built-in admin remains
separate at `/django-admin/` and is not the normal host review surface.

## Operator Checklist Before Host Review

Before sending the staging URL to hosts, confirm:

- DNS for the staging FQDN points at the staging VPS.
- `deploy/inventory/hosts.yml` and `deploy/group_vars/staging.yml` contain the
  real Django Chat staging host and FQDN, not `.example.invalid` placeholders.
- `.sops.yaml` contains the intended age public recipient or recipients.
- `SOPS_AGE_KEY_FILE` points to the matching private key outside this repo.
- `deploy/secrets/staging.sops.yml` exists, decrypts through SOPS/age, and
  contains only Django Chat staging secrets.
- The staging media bucket and public media host are Django Chat-specific.
- Ansible dependencies have been installed locally with `just deploy-bootstrap`.
- `just deploy-bootstrap-target staging` has completed successfully.
- `just deploy-staging` has completed successfully.
- Migrations have run on staging.
- The fixture-backed sample has been imported against the deployed site, using
  the deployed environment and production settings for the
  `import_django_chat_sample` management command.
- Audio has been copied only if the operator intentionally approved running the
  same deployed management command with `--copy-audio`, because that downloads
  real MP3 files into configured media storage.
- `https://<staging-fqdn>/`, `/episodes/`, at least one episode detail page,
  and `/cms/` return expected HTTPS responses.
- Static assets load, and media playback is verified if sample audio was
  copied.

## Admin Access

Host Wagtail accounts should be created only after staging is deployed and the
host account list is approved. Use Django or Wagtail management commands on the
deployed site, or create accounts through Wagtail admin.

Do not commit, document, or print admin passwords in this repository. Share
temporary passwords or password-reset links through the agreed secure channel,
then ask reviewers to change passwords on first use when practical.

## First Review Pass

Hosts should start with:

1. Open the site root and confirm it reaches the episode experience.
2. Browse `/episodes/` and confirm episode titles, dates, descriptions, show
   artwork, navigation, menu links, social links, and distribution links feel
   recognizable for Django Chat.
3. Open at least one episode detail page and review the show notes, metadata,
   audio area, and current URL shape.
4. If sample audio was copied, play an episode and confirm the media URL and
   browser playback behavior are acceptable for review.
5. Log into `/cms/`, inspect the podcast and sample episode pages, and try a
   harmless draft edit without publishing over reviewed content.

## Useful Feedback Categories

When reporting feedback, include the category and the page URL:

- Blocking: anything preventing login, browsing, editing, playback, or review.
- Content: title, description, episode metadata, show notes, artwork, menu,
  social, or distribution link issues.
- Design: Django Chat visual identity, readability, spacing, and differences
  from Simplecast that matter to hosts.
- Playback and media: audio player behavior, media URLs, file availability,
  loading time, or browser compatibility.
- Admin workflow: Wagtail editing, preview, publishing, account permissions,
  or confusion in the CMS.
- Migration questions: production feed, DNS, redirects, analytics, transcripts,
  podcast directories, or full-catalog import decisions.

Do not include passwords, secret URLs, SOPS output, database credentials, S3
credentials, Mailgun keys, Sentry DSNs, or age keys in feedback tickets or
repository comments.

## Known Limitations

- The staging site is not live until real operator inputs are provided and the
  deployment commands complete.
- The first staging import is expected to use the fixture-backed sample unless
  hosts explicitly ask for a larger catalog sample.
- The staging feed is for validation only and is not the canonical Django Chat
  podcast feed.
- No production DNS, feed redirect, Simplecast migration, or podcast directory
  update has been performed.
- Simplecast analytics, distribution analytics, and any Simplecast-specific
  player behavior are not reproduced by this scaffold.
- Transcript conversion and the `cast_transcripts` database worker remain
  disabled unless transcript publishing is explicitly added for staging.
