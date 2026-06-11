# Import Pipeline Security Hardening

The catalog/sample/staging importers ingest content from third-party sources
(Simplecast API + RSS, and the staging Podlove API). That content is treated as
**untrusted**: a compromised, typo-squatted, or MITM'd upstream could otherwise
inject script into the site or steer server-side fetches at internal hosts. The
import code enforces three boundaries on the way in.

## 1. Show-note HTML is sanitized before storage

Imported show notes are stored as Wagtail `RichText` block values and rendered
**without** autoescaping (`richtext` / `expand_db_html` do not sanitize at render
time — only the editor widget does, and the importer bypasses it). So every HTML
string that becomes a stored block value is passed through
`sanitize_show_note_html()` (`django_chat/imports/show_notes.py`) first:

- Allowlist of tags (`p`, `a`, `ul`/`ol`/`li`, `h1`–`h6`, `strong`/`em`/…). Any
  other tag is unwrapped (text kept); known-dangerous containers (`script`,
  `style`, `iframe`, `svg`, `math`, `object`, …) are dropped with their contents.
- All attributes are stripped except a scheme-validated anchor `href` (plus
  `rel`/`target`/`title`). `on*` handlers and inline `style` never survive.
- Comment-like nodes (`Comment`, **`CData`**, `Declaration`, `Doctype`,
  `ProcessingInstruction`) are removed to defeat a CDATA parser-differential mXSS.
- Anchor and markdown-link hrefs are restricted to `http`/`https`/`mailto`.

This applies to the overview block, the title fallback, the paragraph fallback,
and serialized sponsor/link-list copy/intro.

## 2. Imported source-link URLs are scheme-checked

Menu, social, and distribution links from the Simplecast site/distribution
endpoints render directly into `href` attributes. `_safe_link_url()`
(`django_chat/imports/source_data.py`) drops any link whose URL is not
`http`/`https`/`mailto`, so a `javascript:`/`data:` link from a tampered feed is
discarded rather than stored.

## 3. Outbound fetches are SSRF-guarded

`django_chat/imports/url_safety.py` provides `safe_urlopen()`, used by every
default fetcher (catalog text/JSON, audio, cover image, staging transcript):

- Only `http`/`https` targets are allowed (blocks `file://`, which `urllib`
  otherwise honours and would read local files).
- The connection is **pinned**: the host is resolved at connect time and the
  socket connects to that exact globally-routable IP, rejecting any resolution
  that yields a private/loopback/link-local/reserved/CGNAT address (notably the
  cloud metadata endpoint `169.254.169.254`). Resolving and connecting in one
  step closes the DNS-rebinding TOCTOU. TLS SNI/cert validation still uses the
  original hostname.
- HTTP redirects are re-validated and re-pinned, so a public host cannot 30x the
  fetch to an internal address.

The staging transcript importer additionally never fetches a URL string taken
from the remote page body: it reads the custom player's JSON payload, validates
the `audioId` and `post_id` values as integers, and rebuilds the Podlove API
URL on the episode page's **own origin** (`extract_podlove_api_url`), so a
tampered payload cannot steer the follow-up fetch off-host.

## Remediation of already-imported data

The guards above protect *new* imports. Two data migrations re-clean rows stored
before the guards existed (they are near no-ops for the real, benign feed):

- `imports/0013_sanitize_imported_show_note_html` re-runs the sanitizer over each
  *imported* episode body's `overview`/`detail` RichText values (paragraph HTML,
  `show_note_link_list.intro` + `items[].description`, `show_note_sponsor.copy`),
  leaving non-show-note blocks (images, embeds) untouched
  (`sanitize_imported_episode_bodies`). It is scoped to episodes with
  `EpisodeSourceMetadata` so manually authored episodes — whose editor rich text
  may contain Wagtail internal links (`<a linktype="page" id="…">`) the sanitizer
  would strip — are never modified.
- `imports/0014_drop_unsafe_imported_source_links` deletes any stored
  `PodcastSourceLink` whose URL is not http(s)/mailto
  (`drop_unsafe_source_links`).

## Operator-visible behavior

- Imported show notes/links containing disallowed markup or unsafe URL schemes
  are silently stripped/dropped during import (this is intended).
- An import will raise `UnsafeURLError` and abort the offending fetch if a source
  URL points at a non-public address or a non-http(s) scheme.

## Known unfixed issues

Residual, deliberately-unfixed findings (low severity, author-privileged,
deployment-assumption-dependent, or excluded classes) are listed in
[`security-known-issues.md`](security-known-issues.md).

## Tests

`django_chat/imports/tests/test_security_hardening.py` covers the sanitizer
(including the CDATA mXSS case), the link-scheme guard, the SSRF/private-address
and `file://` rejections, the connection-pin resolver, and the staging same-host
check.
