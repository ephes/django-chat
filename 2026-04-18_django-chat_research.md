# Django Chat Self-Hosting Research PRD

Date: 2026-04-18
Repo: `/Users/jochen/projects/django-chat`

## Request Restatement

Investigate how difficult it would be to self-host `djangochat.com`, which is currently served by Simplecast. The likely implementation path is to create a Django/Wagtail/django-cast site in this empty repo that looks like Django Chat and is operated in the same general style as `../python-podcast`: same kind of project layout, local `just` commands, staging deployment path, Wagtail admin, and media storage approach. `python-podcast` is a structural reference, not a source of Django Chat code, content, design, or runtime behavior to copy wholesale.

The research should answer:

- Which `python-podcast` structure and workflow patterns should be mirrored?
- How should episode content, media, artwork, and transcripts be imported?
- What infrastructure changes are needed for staging, and how much of that should live outside this public/shareable app repo?
- Whether Django Chat should get its own S3 bucket and credentials.
- How much work is involved in matching the existing Django Chat design.
- What repository, staging, and deployment access can safely be given to the hosts.
- What work remains before a real production migration away from Simplecast.

## Current State

`django-chat` is currently an empty Git repo: it has `.git` only, no Django project, no app code, no docs, and no deployment wiring.

`python-podcast` is a deployed Django/Wagtail/django-cast project. It uses:

- `django-cast`, `cast-bootstrap5`, and `cast-vue`.
- Wagtail pages for podcast/blog content.
- `cast.Audio`, `cast.Episode`, and `cast.Podcast`.
- S3-compatible media storage through `django-storages`.
- WhiteNoise for static files.
- `ops-control` playbook `playbooks/deploy-python-podcast.yml`.
- `ops-library` role `local.ops_library.wagtail_deploy`.

For Django Chat, these are reference points for repository shape and operator ergonomics only. The new app should have its own name, settings, templates, theme, import code, media bucket, secrets, and deployment target. It should not inherit Python Podcast-specific apps, social links, copy, legal pages, analytics settings, or branding. The transcript worker pattern is the one exception to evaluate deliberately, because Python Podcast already uses it for django-cast transcript work.

`ops-library` already has a generic `wagtail_deploy` role that provisions:

- service user and app path under `/home/<service>/site`
- uv-managed Python environment
- PostgreSQL database and user
- `.env` file
- migrations, collectstatic, and search index update
- systemd service
- Traefik dynamic config

Python Podcast uses `django_tasks.backends.database` plus a `cast_transcripts` database task backend, and its deployment enables a `db_worker` service with `wagtail_db_worker_backend: "cast_transcripts"`. Django Chat should include the same transcript-worker capability if transcript import, conversion, or django-cast transcript publishing is part of the staging proof of concept. Keep this scoped to transcript work; it should not become a general-purpose background-job architecture.

## Public Django Chat Source Data

Sources checked:

- Site: `https://djangochat.com/`
- RSS feed: `https://feeds.simplecast.com/WpQaX_cs`
- Simplecast unauthenticated podcast endpoint: `https://api.simplecast.com/podcasts/19d48b52-7d9d-4294-8dbf-7f2739ba2e91`
- Simplecast unauthenticated episode list endpoint: `https://api.simplecast.com/podcasts/19d48b52-7d9d-4294-8dbf-7f2739ba2e91/episodes?limit=3`
- Simplecast unauthenticated episode lookup endpoint: `https://api.simplecast.com/episodes/search`

Observed on 2026-04-18:

- RSS feed generator: Simplecast.
- Published RSS items: 201.
- Latest RSS item: episode 200, `Django Tasks - Jake Howard`, published 2026-04-15 08:00 UTC.
- Oldest RSS item: episode 0, `Preview`, published 2019-02-02 01:56 UTC.
- RSS audio enclosures: 201 MP3 files.
- RSS-reported audio size: about 11.0 GB total, about 54.7 MB average per episode.
- RSS transcript tags: 0.
- Podcast metadata includes title, description, author, categories, artwork, copyright, language, explicit flag, keywords, and feed URL.
- The unauthenticated Simplecast endpoints observed during research expose the podcast metadata, paginated published episodes, slugs, episode IDs, episode numbers, summaries, descriptions, long descriptions, MP3 URLs, duration, and per-episode detail objects.
- A small spot check of per-episode detail responses found `transcription` HTML. Full-catalog transcript availability is unknown. This is useful, but it should be treated as an undocumented, unauthenticated endpoint dependency unless the hosts can confirm Simplecast export/API guarantees.

Important distinction:

- RSS import is stable and should be the minimum fallback.
- Endpoint-assisted import is much richer and appears suitable for staging, but it carries a higher change risk because the unauthenticated endpoints are not the canonical podcast distribution contract.

## Observed Site Structure

The current Django Chat site is a Simplecast site, and many arbitrary paths return a generic Simplecast page with HTTP 200. Route existence cannot be inferred from status codes alone. Confirmed or useful public surfaces are:

- Home / episode index: `https://djangochat.com/` and `https://djangochat.com/episodes`
- Episode detail pages: `https://djangochat.com/episodes/<slug>`
- Transcript pages: `https://djangochat.com/episodes/<slug>/transcript`
- RSS feed: `https://feeds.simplecast.com/WpQaX_cs`
- Menu links from the Simplecast site API:
  - YouTube: `https://www.youtube.com/@djangochat`
  - Sponsor Us: a Google Docs sponsorship document
  - Fosstodon: `https://fosstodon.org/@djangochat`
- Social link from the Simplecast site API:
  - Fosstodon: `https://fosstodon.org/@djangochat`
- Distribution links from the Simplecast podcast API:
  - Apple Podcasts
  - Overcast
  - Google Podcasts, if still present in the Simplecast data; treat as stale because Google Podcasts was deprecated in 2024
  - Pocket Casts
  - YouTube
  - Amazon Music and Audible
  - Spotify

No separate local About, Contact, Hosts, Sponsors, Privacy, Terms, Support, or Archive page was confirmed from the public Simplecast configuration. The sponsorship entry is an external menu link, not a local `/sponsors/` page. The Simplecast site configuration has `privacy_policy_link: null`, `privacy_policy_text: null`, and `legacy_hosts: null`.

Initial Django Chat page requirements:

- Keep the public episode URL shape: `/episodes/<slug>`.
- Provide `/episodes/<slug>/transcript` for imported transcripts when available.
- Make `/` and `/episodes/` usable as the show landing / episode index. If django-cast internally prefers a podcast page such as `/show/`, add redirects or route aliases so the current Django Chat public URLs remain valid.
- Recreate the Simplecast menu/social/distribution links as configurable site settings or Wagtail-editable snippets.
- Do not create placeholder About, Contact, Hosts, Sponsors, Privacy, Terms, Support, or Archive pages for staging unless the hosts provide content or explicitly ask for them.

Python Podcast pages/features that should not be copied by default:

- German legal pages: `/impressum/` and `/datenschutzerklaerung/`, unless the Django Chat operator/legal context requires equivalents.
- Public user profile pages and account signup/login flows. Wagtail admin accounts are enough for host review.
- Comment URLs under `/show/comments/`, unless the hosts want public comments.
- Fediverse proxy routes such as `.well-known/webfinger`, `@jochen`, and `@show`. Django Chat currently only needs external Fosstodon links.
- DRF token endpoints and public API routes, unless a concrete integration needs them.
- Python Podcast-specific Podlove player template/config endpoints, unless the selected player requires them for Django Chat.

## Feasibility

Self-hosting is feasible. The lowest-risk technical base is to build a fresh Django Chat app with the same kind of architecture as `python-podcast`: Django, Wagtail, django-cast, S3-backed media, local `just` commands, and a staging deployment workflow. This should be a clean implementation for Django Chat, not a renamed copy of Python Podcast.

The project splits into two scopes:

1. Staging proof of concept: import content and media, deploy to a staging domain, provide admin/repo access, and let hosts judge fit.
2. Production migration: preserve podcast client continuity, redirect or replace the canonical feed, update podcast directories, and decide whether audio distribution and analytics move fully away from Simplecast.

The staging proof of concept is moderate effort because the local deployment pattern already exists. Production migration is higher-risk because podcast feed continuity, media URLs, analytics, and Simplecast redirects need host participation.

## Proposed MVP

Build a staging Django Chat site with:

- Django/Wagtail/django-cast project organized like `python-podcast`, but implemented as a Django Chat-specific project.
- Podcast landing / episode index available at `/` and `/episodes/`.
- Episode detail pages preserving the current `/episodes/<slug>` URL shape.
- Transcript pages at `/episodes/<slug>/transcript` when transcripts are imported.
- Imported podcast metadata from RSS plus the unauthenticated Simplecast endpoints.
- Imported published episodes as `cast.Episode` pages.
- Imported MP3 media into a new S3 bucket.
- Imported show notes into the episode body.
- Imported transcripts when practical, either as transcript pages, stored in episode content for review, or converted into django-cast transcript files.
- Transcript task-worker support following the Python Podcast `cast_transcripts` pattern if django-cast transcript import/conversion is included in staging.
- Basic Django Chat branding: title, artwork, colors, navigation, episode list, episode detail, audio player, feed detail.
- Staging deployment at a subdomain such as `django-chat.staging.django-cast.com`.
- Wagtail admin accounts for the hosts.
- Read access to this repo for hosts.

This MVP should not redirect the live Simplecast feed, change `djangochat.com` DNS, or alter podcast directory listings.

## Import Strategy

Preferred import path:

1. Fetch canonical RSS feed.
2. Fetch Simplecast unauthenticated podcast endpoint metadata for additional fields.
3. Fetch paginated Simplecast unauthenticated episode lists for slugs and IDs.
4. Fetch per-episode detail endpoint objects for long descriptions and transcripts.
5. Fetch Simplecast site configuration for menu/social links and distribution channel links.
6. Download or stream-copy MP3 files to the Django Chat media bucket.
7. Create `cast.Audio` objects with `mp3` files and duration metadata.
8. Create `cast.Episode` pages under a `cast.Podcast` page while preserving `/episodes/<slug>` public URLs.
9. Store the Simplecast GUID, API ID, slug, source URL, original enclosure URL, and import timestamp in a local import metadata field/model so re-runs are idempotent.

Fallback import path:

1. Use RSS only.
2. Import 201 episodes with titles, dates, summaries/show notes, GUIDs, audio enclosures, duration, explicit flag, and episode number.
3. Generate slugs locally from episode numbers/titles.
4. Configure menu/social/distribution links manually from the observed Simplecast site configuration.
5. Skip transcripts or import them later.

Open implementation question:

- django-cast's `Transcript` model expects Podlove JSON, WebVTT, and/or DOTe transcript files. The Simplecast detail responses spot-checked during research expose transcripts as HTML. For MVP, store HTML transcripts directly on the episode page or create a simple transcript page. For production-quality podcast transcript support, add conversion to WebVTT/Podlove/DOTe or extend the import path.
- If transcript conversion uses django-cast's transcript processing path, configure `django_tasks` like Python Podcast: a default immediate backend for normal app behavior and a `cast_transcripts` database backend for transcript tasks. Local/test settings can use immediate backends, but staging should run the database worker when transcript jobs are expected.

## Media Storage

Create a new S3 bucket and credentials for Django Chat.

Do not reuse the `python-podcast` bucket or IAM credentials. Reasons:

- Least privilege: Django Chat should not be able to read/write Python Podcast media.
- Operational clarity: backups, lifecycle policies, cost tracking, and cleanup stay separate.
- Avoid namespace collisions and accidental overwrites.
- Existing `wagtail_deploy` and `python-podcast` settings expect a single bucket name and credentials per service, not a shared bucket with per-service prefixes.
- If Django Chat is later transferred or administered with the hosts, separate credentials make ownership boundaries cleaner.

Staging media options:

- Best staging fidelity: copy all MP3s to the new bucket. Size is about 11 GB, which is manageable.
- Faster content-only proof: import metadata and defer audio copy, but this is not a real self-hosting test because playback still depends on Simplecast/CDN URLs.

Recommendation:

- Use a separate staging bucket now.
- Use a separate production bucket later if the migration proceeds.
- Keep decrypted credentials and age private keys outside this shareable app repo.
  If deployment is self-contained, store only SOPS/age-encrypted environment
  secret files in this repo. If a private `ops-control` checkout is used as a
  one-off fallback, credentials can stay in its SOPS files for that fallback
  run.

## Deployment Work

The app repo should expose the same style of operator commands as `python-podcast`, especially:

- `just install`
- `just test`
- `just manage ...`
- `just deploy-staging`
- `just deploy-production`

Those commands should not require third parties to receive access to private
deployment repositories. The preferred target is a self-contained Django
Chat-specific deployment under `deploy/`, with `ops-control` retained only as a
possible one-off bootstrap fallback for the first operator-run staging deploy.
The self-contained deployment must also converge a clean Ubuntu/Debian VPS,
similar to the old `marina` bootstrap flow, not only redeploy onto an already
prepared staging machine.

`deploy-staging` and `deploy-production` should depend on a `deploy-bootstrap`
recipe or equivalent setup step. Bootstrapping should install Ansible
collections from `deploy/requirements.yml` via `ansible-galaxy`. The reusable
`ops-library` collection should be installed from Git by pinned commit SHA until
proper Git tags exist; once `ops-library` tags are pushed, switch the pin to a
tag. Include third-party collections explicitly, including
`community.postgresql`, `community.general`, `community.sops`, and
`ansible.posix`, so bootstrap does not depend on hidden out-of-band installs.
Run Ansible via `uvx --from ansible-core ansible-playbook` or a documented
equivalent, so `uv` is part of the operator toolchain unless a different backend
is chosen.

Deployment backend options:

1. Private `ops-control` backend, invoked from this repo.
   - The Django Chat repo contains `just deploy-staging` and `just deploy-production`.
   - Those recipes check for a local `OPS_CONTROL` path and call the private playbook when present.
   - Hosts can see the command interface, but not private inventories, hostnames beyond what is documented, SOPS secrets, or unrelated services.
   - Effort: about 0.5 to 1.5 days if the playbook is modeled privately on the Python Podcast deployment pattern.
   - Useful only as a one-off bootstrap fallback for the first operator-run
     staging deploy; not the recommended ongoing path.

2. External deployment repo for Django Chat.
   - Create a separate deploy repo that contains only Django Chat deployment code, inventory templates, and encrypted secrets policy.
   - This repo can be private to you, shared with hosts later, or transferred independently.
   - The app repo `just` commands call `DJANGO_CHAT_DEPLOY_REPO` or `DEPLOY_REPO`.
   - Effort: about 1 to 2 days if it wraps existing private ops-control patterns; about 3 to 6 days if it replaces them with a fully independent Ansible/pyinfra setup.
   - Best if hosts should understand or eventually own deployment without seeing unrelated personal infrastructure.

3. Self-contained deployment in this app repo.
   - Put deploy playbooks/scripts under `deploy/`.
   - Keep only templates and non-secret defaults in Git.
   - Store SOPS/age-encrypted secret files under `deploy/secrets/`; keep
     decrypted files and age private keys outside the repo.
   - Add `.sops.yaml` with age public recipients so re-encryption and future
     handoff are explicit.
   - Install reusable Ansible dependencies through `deploy/requirements.yml`
     rather than requiring operators or hosts to check out `ops-library`.
   - Effort: about 2 to 4 days for a staging-quality deploy path; more for production-grade backup/restore, secret rotation, and multi-environment hardening.
   - Best if the repo is intended to be a complete handoff artifact, but it increases the chance that deployment details leak into a repo shared with third parties.

Recommended initial path:

- Keep the app repo command surface stable: `just deploy-staging` and `just deploy-production`.
- Make self-contained deployment in this app repo the primary implementation
  path.
- Implement `deploy/` with a narrow Django Chat playbook, minimal inventory,
  host vars, SOPS/age-encrypted secrets, `.sops.yaml`, and
  `deploy/requirements.yml`.
- Include an empty-VPS bootstrap path for Hetzner/Strato-style instances:
  baseline host tasks first, then `uv`, Traefik base install, PostgreSQL, app
  Python, application user, systemd services, and HTTPS. The strict role order
  is listed below.
- Do not give Django Chat hosts access to `ops-control`.
- Do not require Django Chat hosts to check out `ops-library`; install it via
  `ansible-galaxy` from a pinned Git commit SHA until tags exist.
- Do not copy `ops-control` private helpers such as
  `playbooks/common/load_service_secrets.yml` or `services-metadata.yml`.
  The Django Chat playbook should load its own SOPS file directly with the
  `community.sops.sops` lookup.
- Treat the old `python-podcast/deploy/` and `marina/deploy/` directories as
  historical reference only. They use Ansible Vault conventions and should not
  be used as templates for Django Chat.
- Document operator workstation prerequisites in `docs/operations-boundary.md`:
  `uv`, `just`, `sops`, `age`, Ansible execution through `uvx`, and the age
  private key path via `SOPS_AGE_KEY_FILE`.
- If the project later needs a stricter ownership boundary than encrypted
  secrets in the app repo can provide, split a narrow Django Chat deployment
  repo rather than exposing the broader `ops-control` repo.

If using the self-contained backend, expected service settings are:

The following details are operator-facing planning context. They are useful for
implementation, but they should not be copied into host-facing documentation or
public setup instructions.

- Service name: likely `django-chat`.
- Source path: an absolute path to the local Django Chat checkout on the
  operator workstation, for example `/Users/<operator>/projects/django-chat`.
  For rsync deploys this is the repository root, not `/`.
- Deployment method: `rsync` for staging.
- App port: choose an unused port, for example `10015`.
- Host baseline: target a fresh Ubuntu 24.04 LTS VPS first. Ubuntu 22.04 LTS
  and Debian 12 are acceptable secondary targets. Current `wagtail_deploy`
  defaults derive the PostgreSQL repository codename from
  `ansible_distribution_release`, so host-var overrides should only be needed
  for distro-specific exceptions or nonstandard provider images. The instance
  needs root or sudo SSH access, public DNS already pointing at the server, and
  inbound ports 22, 80, and 443 reachable. The deploy should install required
  OS packages itself rather than assuming the server was prepared by
  `ops-control`.
- Role order for a clean VPS: run baseline host tasks first, then
  `local.ops_library.uv_install`, then `local.ops_library.traefik_deploy`, then
  `local.ops_library.wagtail_deploy`. `wagtail_deploy` can also invoke
  `uv_install` during app Python setup, but the clean-VPS bootstrap should make
  the uv prerequisite explicit. Baseline host tasks should include `apt` cache
  refresh, the minimal packages Ansible and deploy need on the target, hostname
  setup if desired, swap when the provider image does not include it, and an
  SSH-preserving firewall rule before any firewall tightening.
- Reverse proxy: run `local.ops_library.traefik_deploy` or an equivalent
  self-contained Traefik bootstrap before `wagtail_deploy`, because
  `wagtail_deploy` writes service dynamic config but does not install the base
  Traefik service.
- Traefik settings: provide `traefik_letsencrypt_email` in host vars or SOPS
  secrets before running the clean-VPS bootstrap. If using the role's firewall
  support, preserve SSH explicitly before enabling or tightening any firewall.
  The Traefik role opens HTTP/HTTPS when UFW is installed, but the Django Chat
  bootstrap must not risk locking out port 22.
- Python/runtime: use the `wagtail_deploy` uv path for app Python. It can
  install the requested Python version with uv, so the old `marina` source-built
  Python task should not be copied.
- Database: rely on `local.ops_library.postgres_install` through
  `wagtail_deploy` for local PostgreSQL provisioning on the VPS.
- Memory sizing: a 4 GB VPS should be enough for Django/Wagtail/django-cast,
  local PostgreSQL, Traefik, 2 to 3 Gunicorn workers, and an optional transcript
  database worker when media is S3-backed. Avoid local media storage and heavy
  transcript/ML work on the VPS. Heavy transcription/ML inference runs on the
  operator's Mac Studio, not on the VPS; the VPS carries at most a lightweight
  `cast_transcripts` database worker for publishing or conversion of
  transcripts produced elsewhere. Add swap if the provider image does not
  include it.
- Inventory shape: use one combined inventory with staging and production
  hosts/groups, plus environment-specific host vars. The inventory can commit
  staging/production FQDNs and app ports; operational secrecy comes from SOPS,
  not from hiding hostnames.
- Transcript worker, if enabled:
  - `wagtail_db_worker_enabled: true`
  - `wagtail_db_worker_backend: "cast_transcripts"`
  - keep the default queue name and interval unless transcript volume or latency requires tuning
- Host vars:
  - `django_chat_wagtail_fqdn: django-chat.staging.django-cast.com`
  - `django_chat_traefik_host_rule: Host(\`django-chat.staging.django-cast.com\`)`
  - `django_chat_django_allowed_hosts: django-chat.staging.django-cast.com,localhost`
  - `traefik_letsencrypt_email`
  - `wagtail_admin_url`, if Django Chat should override the role default
    `hidden_admin/`
  - explicit `wagtail_staticfiles_required_paths` matching the installed
    django-cast/cast-bootstrap5 assets, rather than inheriting an app-specific
    list by accident
- Secrets:
  - `django_secret_key`
  - `postgres_password`
  - `django_aws_access_key_id`
  - `django_aws_secret_access_key`
  - `django_aws_storage_bucket_name`
  - `cloudfront_domain`, treated as the required public media host for the
    deployed site. For staging, use a real CloudFront distribution if available;
    otherwise use the S3/object-storage public host only if Django settings
    support that host as the media custom domain. Do not use an empty value or
    placeholder without first changing `wagtail_deploy`, because the role
    requires a non-empty non-`CHANGEME` value.
  - `django_sentry_dsn`
  - `django_mailgun_api_key`
  - `mailgun_sender_domain`
  - `django_server_email`

Consider separate age recipients for staging and production from the start.
That keeps later production handoff possible without replacing the original
operator's staging key.

Enable the `wagtail_deploy` database worker for Django Chat when transcript import/conversion uses the django-cast transcript task path. If transcripts are deferred or stored only as plain episode/page content, keep the worker disabled for that environment. In either case, keep `TASKS["default"]` immediate/synchronous and reserve the database backend for `cast_transcripts`.

Backups:

- For staging proof of concept, database backup can be deferred or implemented with the same shape as the Python Podcast staging backup pattern.
- Before production, define database and media backup/restore. Existing Python Podcast media backup patterns can guide the design, but Django Chat should use its own backup service and prefix.

## Design and Templates

The current Simplecast site is a JavaScript app with Simplecast-hosted CSS/assets. The static HTML shell is minimal, so directly copying the visual design from rendered HTML is not straightforward.

Practical design options:

1. Minimal branded django-cast theme:
   - Use existing Bootstrap 5/django-cast templates.
   - Add Django Chat artwork, colors, typography, and navigation.
   - Fastest and enough for staging.

2. Closer Simplecast visual match:
   - Inspect rendered Simplecast app in browser.
   - Recreate key layouts in local templates.
   - Avoid depending on Simplecast JS/CSS.
   - More work but gives hosts a realistic visual comparison.

3. Full redesign:
   - Treat the self-hosted site as a chance to improve the site.
   - Requires host feedback and is out of scope for the first proof of concept.

Recommendation:

- Start with option 1.
- Add only enough template customization to make it clearly Django Chat.
- Preserve the current public URL structure before spending time on additional static pages.
- Treat menu/social/distribution links as part of the visual and navigational parity work.
- Ask hosts whether visual parity matters after they can click through imported content.

## Repository And Host Access

Giving hosts access to this repo is safe if:

- The repo does not contain decrypted secrets.
- Deployment secrets committed to the repo are SOPS/age-encrypted and scoped to
  Django Chat only.
- Age private keys remain outside the app repo.
- S3 credentials, database passwords, Sentry DSNs, Mailgun keys, and admin
  passwords are never committed in plaintext.
- The repo contains documentation explaining the split between app code,
  encrypted deployment material, and off-repo private keys.

Recommended access:

- GitHub read access or collaborator access to `django-chat`.
- No access to `ops-control` by default.
- Wagtail admin accounts on staging for content review.
- Optional issue tracker access for feedback.

Deployment access can be separate from code access:

- Reviewers can read the Django Chat app repo and use staging without seeing
  decrypted secrets or unrelated infrastructure.
- Operators keep age private keys and any private operator notes elsewhere.
- If hosts later need a stricter deployment ownership boundary than encrypted
  secrets in this app repo provide, create a narrow Django Chat deployment repo
  rather than sharing the broader private operations repository.

## Documentation Plan

Start with lightweight Markdown documentation in this repo. A full Sphinx/Furo
documentation site like `../django-cast` is useful for a reusable library, but
it is too much ceremony for the first Django Chat staging proof of concept.
GitHub-readable Markdown is easier for hosts to open, review, and comment on.

Keep this PRD at the repository root as the dated research record:

- `2026-04-18_django-chat_research.md`

After the project scaffold exists, add:

- `README.md`
- `docs/host-review-guide.md`
- `docs/staging-differences.md`
- `docs/local-development.md`
- `docs/operations-boundary.md`
- `docs/production-migration-notes.md`

Recommended contents:

- `README.md`
  - Short project overview.
  - Current project status.
  - Link to this PRD.
  - Link to the host review guide.
  - Local developer commands once the scaffold exists.
- `docs/host-review-guide.md`
  - Staging URL and admin URL.
  - What hosts should try first.
  - What feedback is useful.
  - Known limitations of the staging instance.
  - How to report issues.
- `docs/staging-differences.md`
  - Why the staging site can differ from Simplecast.
  - Different web player.
  - Different visual theme if the first version uses django-cast/Bootstrap.
  - No Simplecast analytics in the staging test.
  - Feed is not canonical yet.
  - Distribution links are represented but not a production migration state.
  - Google Podcasts may appear as stale upstream data.
  - Transcript rendering may differ from Simplecast.
  - Episode catalog may be partial during early staging.
  - Audio may be sample-only or S3-backed depending on staging phase.
- `docs/local-development.md`
  - `just install`
  - `just manage ...`
  - `just test`
  - Environment file expectations.
  - Explicit note that deployment is handled separately from local development.
- `docs/operations-boundary.md`
  - Self-contained app-repo deployment model.
  - Why hosts can deploy Django Chat without seeing `ops-control`.
  - What lives in this repo: `deploy/`, encrypted SOPS files, inventory,
    host vars, playbooks, and non-secret defaults.
  - What stays off-repo: decrypted secrets, age private keys, private operator
    notes, and unrelated infrastructure inventory.
  - Operator workstation prerequisites: `uv`, `just`, `sops`, `age`, Ansible
    via `uvx`, and `SOPS_AGE_KEY_FILE`.
  - Workstation bootstrap runbook: generate or choose an age key, back up the
    private key outside the app repo, add the public recipient to `.sops.yaml`,
    create/edit SOPS files, run `just deploy-bootstrap`, then run the target
    deploy command.
  - Target VPS prerequisites: supported Ubuntu/Debian image, root or sudo SSH
    access, DNS for the staging/production FQDN, ports 80/443 open for Let's
    Encrypt, and S3/object-storage credentials prepared.
  - Clean-VPS bootstrap tasks: `apt` cache refresh, minimal target packages,
    optional hostname setup, swap if absent, SSH-preserving firewall rule, then
    `uv_install`, `traefik_deploy`, and `wagtail_deploy`.
  - `ops-library` dependency policy: install through `ansible-galaxy` from a
    pinned Git commit SHA until tags exist, then move to a tag.
  - What `just deploy-staging` means once deployment commands exist.
- `docs/production-migration-notes.md`
  - Feed redirect risks.
  - GUID preservation.
  - Canonical domain decisions.
  - Simplecast redirect and podcast directory coordination.
  - Analytics, CDN, and ad insertion questions.

Do not move this PRD into `docs/` immediately. It is easier to find while the
repo is still mostly empty, and it is a historical research artifact rather
than host-facing product documentation. Once the scaffold and docs structure
exist, add `README.md` links to both this PRD and the host-facing docs. If the
documentation grows large enough to need navigation, search, or versioned
publishing, migrate `docs/` to Sphinx/Furo later.

Implementation tracking should stay lightweight:

- Prefer GitHub issues or another issue tracker once the repo is shared.
- Until an issue tracker exists, keep the implementation slices in this PRD as
  the canonical backlog.
- Avoid separate `backlog.md` and `done.md` files at the start; they become
  stale easily.
- If local tracking is needed before GitHub issues exist, add a single
  `docs/implementation-status.md` with checkboxes for the PRD slices, links to
  commits/PRs, and a short "next action" section. Do not duplicate the full PRD
  in that file.

## Production Migration Considerations

Production migration is not just deploying the app.

Needs host decisions:

- Should `djangochat.com` continue to be the canonical site domain?
- Should the podcast feed move from Simplecast to django-cast?
- Should Simplecast redirect the old feed to the new feed?
- Should old episode URLs be preserved exactly, redirected, or allowed to change?
- Should audio download URLs be hosted by S3/CloudFront directly, or through another CDN/analytics layer?
- Is Simplecast analytics, distribution, or ad insertion currently required?
- Are transcripts owned/exportable and intended to be published on the self-hosted site?
- Are sponsor mentions/ad markers purely in audio/show notes, or are there dynamic ad features in use?

Podcast feed continuity checklist:

- Generate a new django-cast RSS feed and validate it.
- Compare item GUIDs, titles, dates, durations, enclosure sizes, and episode numbers against Simplecast RSS.
- Preserve existing GUIDs for migrated episodes; GUID changes can cause podcast clients to treat old catalog items as new episodes.
- Verify artwork dimensions and podcast namespace fields.
- Confirm `itunes:new-feed-url` behavior.
- Coordinate Simplecast feed redirect or directory updates with hosts.
- Test Apple Podcasts, Spotify, Pocket Casts, and generic RSS clients before switching.

## Risks

- Simplecast unauthenticated endpoints may change, disappear, add rate limits, or require authentication later.
- RSS does not include transcripts or per-episode slugs.
- Simplecast page HTML is a JS shell, so scraping rendered design/content is more fragile than API/RSS import.
- The Simplecast site can return HTTP 200 for arbitrary paths, so route discovery must rely on API configuration, indexed content, host confirmation, and known episode/transcript URL patterns rather than status-code probes.
- django-cast transcript support expects specific file formats, not Simplecast HTML transcripts.
- Endpoint-assisted import should degrade gracefully to RSS-only import if the unauthenticated Simplecast endpoints become unavailable.
- Downloading/copying 11 GB of MP3s is manageable but still needs repeatable import and retry logic.
- The reference deployment pattern assumes S3/CloudFront-style media settings; local development and staging secrets need care.
- Enabling the transcript database worker adds another systemd service and a small operational surface; monitor it separately from the web app if transcript publishing/conversion jobs are part of staging. Heavy transcription/ML inference should run on the operator's Mac Studio, not on the VPS.
- SOPS/age private keys must be backed up outside the app repo, for example in
  a password manager or hardware-backed secret store. Losing the only age
  private key makes committed SOPS secret files unrecoverable.
- Podcast production migration can break subscribers if feed GUIDs, redirects, or enclosure URLs are mishandled.
- Giving hosts app repo access is fine, but giving access to deployment repositories or ops secrets is a separate security decision.

## Improvements Over The Reference Repo

The Django Chat repo can keep the useful `python-podcast` shape while improving the implementation details:

- Use `prek`, a lightweight pre-commit hook runner, instead of `pre-commit` if the hooks are simple enough. This should reduce hook startup overhead while keeping the same developer workflow.
- Prefer `ruff` for linting and import sorting instead of separate `flake8` plus `isort`. Keep `black` only if there is a strong preference for Black formatting; otherwise evaluate `ruff format` for one-tool consistency.
- Include a Django template formatter such as `djhtml` if the project carries custom templates.
- Pick one environment loading approach early, for example `django-environ` or `python-dotenv`, and document it in the settings and local setup docs.
- Keep deployment commands in `just`, backed by the self-contained `deploy/`
  directory. A private `ops-control` backend can remain as an explicit one-off
  fallback, but should not be required for normal Django Chat operators.
- Make `deploy/` converge a clean VPS as well as update an existing staging
  machine. Bootstrap base packages, Traefik, PostgreSQL, uv/Python, the app
  user, systemd units, and HTTPS in the same documented workflow.
- Avoid a general background-worker architecture. Add the django-cast transcript database worker when transcript import/conversion needs it, and keep other app behavior immediate/synchronous by default.
- Keep local development secrets in `.env`. Keep production/staging secrets
  SOPS/age-encrypted under `deploy/secrets/`, with decrypted values and age
  private keys outside the repo.
- Add a small import test fixture from RSS and captured Simplecast endpoint responses so import behavior is tested without network access.
- Make import commands idempotent from the start by recording source GUID/API IDs.
- Add a feed parity check command, for example `just compare-feed`, before any production migration. Staging can start with a smoke-level feed check; exhaustive GUID, duration, enclosure, and namespace comparison belongs in production hardening.
- Document the operations boundary early so third-party collaborators
  understand that deploy commands require only this repo plus documented local
  tools and age keys, not `ops-control`.
- Keep Python Podcast-only routes out of the initial Django Chat app. Add static/legal/account/comment/Fediverse/API pages only when there is a Django Chat-specific requirement.

## Estimate

Rough effort for staging proof of concept:

- Scaffold Django Chat project using the `python-podcast` structure as a reference: 0.5 to 1 day.
- Rename/project cleanup/settings/docs: 0.5 day.
- Import command for RSS and endpoint-assisted metadata: 1 to 2 days.
- Media copy to S3 and idempotent audio import: 1 to 2 days.
- Transcript task backend and worker wiring: 0.5 day if transcript processing is included in staging.
- Basic templates/branding, menu links, and current URL compatibility: 1 to 2 days.
- Self-contained deployment wrapper, clean-VPS bootstrap, SOPS/age wiring, and
  staging playbook: 2 to 4 days.
- Staging deploy and smoke test: 0.5 to 1 day.
- Host accounts and review docs: 0.5 day.

Likely total for a useful staging review: 5.5 to 9.5 engineering days if transcript worker support is included; 5 to 9 days if transcripts are stored as simple page content or deferred.

Production migration hardening:

- Feed parity tests and validation: 1 to 2 days.
- Transcript conversion/publishing polish: 1 to 3 days.
- Backup/restore and media backup workflow: 1 to 2 days.
- Narrow external deployment repo, if encrypted deployment material in the app
  repo later proves too broad for handoff: 1 to 6 days depending on whether it
  wraps or replaces private ops patterns.
- URL redirect strategy and DNS/feed switch coordination: 1 to 3 days.
- Host review iterations/design polish: variable.

## Suggested Implementation Slices

1. Scaffold the Django/Wagtail/django-cast project with local `just` commands, `README.md`, and no deployment backend yet.
2. Add local settings, environment loading, lint/format hooks, `django_tasks` transcript backend settings, minimal tests, and `docs/local-development.md`.
3. Build a read-only importer for RSS plus captured Simplecast endpoint fixtures, including site menu/social/distribution link fixtures.
4. Add idempotent source metadata and import metadata/pages for a small representative episode sample without copying audio yet.
5. Add S3 media storage and copy audio for the sample import.
6. Add basic Django Chat branding, templates, menu links, and current public URL compatibility.
7. Add smoke-level feed checks against the Simplecast RSS feed, deferring exhaustive parity validation to production hardening.
8. Add self-contained `deploy/`, clean-VPS bootstrap, `just deploy-staging`,
   and `just deploy-production` with SOPS/age secret loading,
   `ansible-galaxy` bootstrap, a pinned `ops-library` dependency, explicit
   static asset checks, and the role sequence `uv_install`,
   `traefik_deploy`, then `wagtail_deploy`. Include the `cast_transcripts`
   database worker only when transcript publishing/conversion jobs are enabled;
   heavy transcription runs on the Mac Studio. Document the boundary in
   `docs/operations-boundary.md` before the first deploy run.
9. Deploy staging, create host admin accounts, and document the review workflow in `docs/host-review-guide.md` and `docs/staging-differences.md`.
10. Decide whether production migration needs a separate follow-up PRD after host review.

## Recommended Next Steps

1. Build the staging proof of concept in this repo using the `python-podcast` repository shape as a reference.
2. Create a Django Chat-specific S3 bucket and SOPS/age-encrypted staging
   secrets, keeping decrypted values and age private keys outside this app repo.
3. Implement an idempotent import command using RSS plus the unauthenticated Simplecast endpoints.
4. Import a small sample first: latest 5 episodes, one 2019 episode, and one transcript-heavy episode.
5. Validate django-cast episode pages, current public URL patterns, audio playback, transcript handling, generated feed, and admin editing.
6. Import the full catalog and media once the sample is clean.
7. Add `deploy/`, clean-VPS bootstrap, `just deploy-staging`, and
   `just deploy-production` commands in this repo using the self-contained
   SOPS/age deployment model.
8. Implement those deploy commands without requiring `ops-control` or a manual
   `ops-library` checkout, including the transcript worker service when
   transcript processing is enabled.
9. Give hosts staging admin access and app repo access.
10. Gather feedback on design fidelity and production migration appetite.

## Acceptance Criteria For The Research Spike

- A staging site exists and loads over HTTPS.
- Hosts can log into Wagtail admin.
- At least a representative sample of episodes is imported with audio playback.
- Current public URL patterns for `/`, `/episodes/`, `/episodes/<slug>`, and `/episodes/<slug>/transcript` are represented or redirected.
- Menu, social, and distribution links from the Simplecast site are represented.
- Transcript handling is demonstrated for at least one representative episode, either as simple page content or through the `cast_transcripts` worker path.
- The full catalog import path is documented and repeatable.
- Media storage is isolated from Python Podcast.
- The generated podcast feed validates for imported episodes.
- The remaining production migration risks are documented before any live feed/DNS change.
