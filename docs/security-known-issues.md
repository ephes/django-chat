# Known Security Issues (Not Fixed)

This records security findings from the codebase review that were **deliberately
not fixed**, with the reason each was accepted and what remediation would look
like if the assumptions change. The high/medium, concretely-exploitable findings
were fixed (see [`import-security.md`](import-security.md)); everything below is
low severity, requires a privileged actor, depends on a deployment assumption, or
falls in an explicitly excluded class.

Re-evaluate this list if the threat model changes — especially if the app is
ever exposed without the assumed reverse proxy, or if untrusted users gain
Wagtail admin access.

## 1. `|safe` on the staff-edited sponsor stat label

- **Where:** `django_chat/templates/cast/django_chat/sponsor.html:39` —
  `{{ stat.label|safe }}` (a `SponsorStat.label` `CharField`).
- **Severity:** Low (author-privileged stored XSS on a public page).
- **Why not fixed:** `SponsorStat` rows are created only through the Wagtail
  admin by trusted staff. A non-privileged attacker cannot reach this field, so
  it does not meet the exploitability bar. A malicious or compromised editor
  account could inject script for public visitors, so this relies on the current
  trusted-staff admin model.
- **If revisited:** Drop the `|safe` filter (the label is plain text — autoescape
  is correct), or sanitize it. Cheap defense-in-depth.

## 2. Sanitizer does not force `rel="noopener noreferrer"` on `target="_blank"`

- **Where:** `django_chat/imports/show_notes.py` — `_SANITIZE_ALLOWED_TAGS`/
  `_SANITIZE_ALLOWED_ATTRS` keep `target` on `<a>` without enforcing `rel`.
- **Severity:** Low (reverse tabnabbing — an explicitly excluded class).
- **Why not fixed:** Modern browsers default `target="_blank"` to `noopener`, and
  the real feed already ships `rel="noopener noreferrer"`. Reverse tabnabbing is
  an excluded finding class for this review.
- **If revisited:** When `name == "a"` and `target` is `_blank`, ensure `rel`
  contains `noopener noreferrer` (mirroring `core/sponsor_shoutout.py`).

## 3. `validate_outbound_url` fails open when a host does not resolve

- **Where:** `django_chat/imports/url_safety.py` — `_is_disallowed_address`
  returns `False` on `getaddrinfo` `OSError`.
- **Severity:** Informational / accepted.
- **Why not fixed:** This pre-check is advisory. The authoritative SSRF defense
  is the connection-time pin (`_resolve_global_ip` inside the pinned connection),
  which re-resolves and **raises** on failure or on any non-global address, and
  is what the socket actually connects to. An unresolvable host fails the real
  fetch regardless, so the fail-open pre-check is not exploitable.
- **If revisited:** Make the pre-check raise on resolution failure too (it would
  only change the error type, not the security outcome).

## 4. `mailto:` hrefs are not explicitly attribute-escaped by the sanitizer

- **Where:** `django_chat/imports/show_notes.py` — `_sanitized_href` returns a
  `mailto:` value unchanged; escaping relies on BeautifulSoup's serializer.
- **Severity:** Low / not exploitable (verified).
- **Why not fixed:** BeautifulSoup chooses an attribute delimiter that the raw
  value cannot break out of (a `"` in the value forces single-quote delimiting,
  etc.), and browsers do not terminate a quoted attribute on `<`. No breakout was
  reachable in testing. It is an implicit dependency on the serializer rather than
  a concrete vulnerability.
- **If revisited:** Explicitly `escape(href, quote=True)` for non-canonicalized
  schemes to make the safety explicit rather than serializer-dependent.

## 5. Sponsor page proxy bypassed Wagtail per-page view restrictions (fixed)

- **Was:** `django_chat/sponsor/views.py` looked the `SponsorPage` up with
  `.live()` and returned `page.serve(request)`. `Page.serve()` does not run
  Wagtail's `before_serve_page` hooks, which is where `PageViewRestriction`
  (login, password, group) is enforced, so `/episodes/sponsor/` would have
  served the full page past any such restriction while Wagtail's own `/sponsor/`
  route showed the login or password form. Latent: no restriction is configured.
- **Fixed:** the lookup uses `SponsorPage.objects.live().public()`, so a
  restricted page, or one under a restricted ancestor, is a 404 on
  `/episodes/sponsor/`. Viewers allowed through the restriction use Wagtail's own
  route. Covered by `django_chat/sponsor/tests/test_sponsor_page.py`.

## 6. `SECURE_PROXY_SSL_HEADER` trusts a client-settable header

- **Where:** `config/settings/production.py:35` —
  `SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")`.
- **Severity:** Accepted under the deployment topology.
- **Why not fixed:** This is safe **only** because the app is not directly
  reachable: gunicorn binds to `127.0.0.1` behind a TLS-terminating reverse proxy
  (traefik) that sets `X-Forwarded-Proto`. A client cannot reach the app to spoof
  the header in that topology.
- **If revisited:** If the app is ever exposed directly (no trusted proxy, or a
  proxy that does not strip/overwrite the header), a client could spoof
  `X-Forwarded-Proto: https` and defeat `SECURE_SSL_REDIRECT` / secure-cookie
  logic. Remove this setting or ensure the proxy always overwrites the header.

## Episode privacy (fixed)

Recorded here because it is the rule that keeps §5 from recurring elsewhere.
The sponsor page proxy (§5) follows the same rule.

- **Was:** the custom episode index (`django_chat/core/views.py`), the embed
  player view, and the latest-entries feed (`django_chat/core/feeds.py`)
  queried `Episode.objects.live()` / `Podcast.objects.live()` without
  `.public()`. These views never call `Page.serve()`, so Wagtail's
  `PageViewRestriction` checks did not run, and login-, password- and
  group-restricted episodes were listed, embeddable and published in
  `/episodes/feed/rss.xml` with their show notes and enclosure. The feed was
  also mounted as one shared instance without django-cast's restricted-root
  guard, so a cached feed kept being served after its podcast was restricted.
- **Fixed:** every page lookup in those views uses `.live().public()`; the feed
  route is wrapped in `unrestricted_page_required(Blog)` (checked before the
  response cache) and `request_local_feed` (one feed instance per cache miss),
  matching django-cast's own feed routes. Once a `PageViewRestriction` save or
  delete commits, the response cache is cleared (`django_chat/core/receivers.py`,
  run via `transaction.on_commit` because production uses `ATOMIC_REQUESTS`).
  The site feed's cache key carries a generation that the clear resets
  (`restriction_aware_cache_page` in `django_chat/core/feeds.py`), so a render
  already in flight during the change stores its stale response where no later
  request reads it.
  Covered by
  `django_chat/core/tests/test_episode_privacy.py`.
- **Rule:** any project view or feed that renders pages without going through
  Wagtail's `serve()` must filter with `.live().public()`, refuse restricted
  roots before any shared cache, and rely on the restriction-change cache
  invalidation for anything it caches.
- **Still accepted:** unpublishing an episode does not invalidate the cache, so
  a cached feed can list it for up to five minutes; that is django-cast's
  upstream behaviour and not a privacy control. django-cast's own cached feeds
  (`/episodes/feed/podcast/<format>/rss.xml`, `/episodes/feed/atom.xml`) are
  also cleared on a restriction change, but use plain `cache_page`: a render in
  flight at that moment can refill them with the old entry for up to five
  minutes. Closing that needs a generation-aware cache in django-cast itself.

## Out of scope (not security defects in this codebase)

- **Vendored `django-cast` migration drift** surfaced by
  `makemigrations --check` (`cast` app, in the pinned dependency) — a dependency
  concern, not a vulnerability here.
- **DoS / rate limiting / resource exhaustion**, outdated-dependency CVEs, and
  secrets-at-rest in SOPS-encrypted or `.example` files were excluded by the
  review scope and are handled by other processes.
