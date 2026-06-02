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

## 5. Sponsor page proxy bypasses Wagtail per-page view restrictions

- **Where:** `django_chat/sponsor/views.py:28` — `return page.serve(request)`
  serves the `SponsorPage` directly instead of going through Wagtail's routing.
- **Severity:** Low / not currently exploitable.
- **Why not fixed:** Calling `page.serve()` skips Wagtail's
  `PageViewRestriction` checks (password/private/group). The `SponsorPage` is a
  public marketing page with no such restriction configured, so there is nothing
  to bypass today.
- **If revisited:** If a view restriction is ever added to that page, route
  through Wagtail's `serve` view (or check `get_view_restrictions()`) so the
  restriction is enforced.

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

## Out of scope (not security defects in this codebase)

- **Vendored `django-cast` migration drift** surfaced by
  `makemigrations --check` (`cast` app, in the pinned dependency) — a dependency
  concern, not a vulnerability here.
- **DoS / rate limiting / resource exhaustion**, outdated-dependency CVEs, and
  secrets-at-rest in SOPS-encrypted or `.example` files were excluded by the
  review scope and are handled by other processes.
