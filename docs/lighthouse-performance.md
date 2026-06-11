# Lighthouse Performance

This note records the staging Lighthouse gate used before host handoff. The
target is near-100 scores on the public host-review surfaces in both mobile and
desktop Lighthouse runs.

## Scope

Measured staging URLs on 2026-04-29:

- `https://djangochat.staging.django-cast.com/`
- `https://djangochat.staging.django-cast.com/episodes/`
- `https://djangochat.staging.django-cast.com/episodes/django-tasks-jake-howard/`
- `https://djangochat.staging.django-cast.com/episodes/feed/`

RSS XML endpoints are checked for HTTP health, not Lighthouse category scores:

- `https://djangochat.staging.django-cast.com/episodes/feed/rss.xml`
- `https://djangochat.staging.django-cast.com/episodes/feed/podcast/mp3/rss.xml`

## Commands

The local machine did not have Chrome installed, so the audit used an
ephemeral Chrome for Testing binary outside the repo:

```sh
npx --yes @puppeteer/browsers install chrome@stable \
  --path /tmp/django-chat-lighthouse-browser \
  --format '{{path}}'
```

Set `CHROME_PATH` to the printed executable path before running Lighthouse.
For the 2026-04-29 runs:

```sh
export CHROME_PATH='/tmp/django-chat-lighthouse-browser/chrome/mac_arm-148.0.7778.56/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing'
mkdir -p /tmp/django-chat-lighthouse-20260429-final2

npx --yes lighthouse https://djangochat.staging.django-cast.com/episodes/ \
  --preset=desktop \
  --output=json --output=html \
  --output-path=/tmp/django-chat-lighthouse-20260429-final2/episodes-desktop \
  --chrome-flags="--headless=new" \
  --quiet

npx --yes lighthouse https://djangochat.staging.django-cast.com/episodes/ \
  --form-factor=mobile \
  --screenEmulation.mobile=true \
  --screenEmulation.width=390 \
  --screenEmulation.height=844 \
  --screenEmulation.deviceScaleFactor=3 \
  --throttling-method=simulate \
  --output=json --output=html \
  --output-path=/tmp/django-chat-lighthouse-20260429-final2/episodes-mobile \
  --chrome-flags="--headless=new" \
  --quiet
```

Repeat the same desktop/mobile commands for each scoped URL, changing only the
URL and output-path prefix. The 2026-04-29 baseline reports are in
`/tmp/django-chat-lighthouse-20260429/`; final reports are in
`/tmp/django-chat-lighthouse-20260429-final2/`.

## Results

Baseline scores before optimization:

| Page | Mode | Performance | Accessibility | Best Practices | SEO | LCP | CLS | TBT |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `/` -> `/episodes/` | desktop | 99 | 94 | 100 | 100 | 0.8 s | 0.06 | 0 ms |
| `/` -> `/episodes/` | mobile | 88 | 94 | 100 | 100 | 3.9 s | 0.022 | 0 ms |
| `/episodes/` | desktop | 100 | 94 | 100 | 100 | 0.8 s | 0 | 0 ms |
| `/episodes/` | mobile | 87 | 94 | 100 | 100 | 4.0 s | 0.022 | 0 ms |
| `/episodes/django-tasks-jake-howard/` | desktop | 87 | 100 | 100 | 100 | 0.8 s | 0.241 | 0 ms |
| `/episodes/django-tasks-jake-howard/` | mobile | 76 | 100 | 100 | 100 | 1.3 s | 0.869 | 90 ms |
| `/episodes/feed/` | desktop | 100 | 100 | 100 | 100 | 0.4 s | 0.001 | 0 ms |
| `/episodes/feed/` | mobile | 100 | 100 | 100 | 100 | 1.3 s | 0.001 | 0 ms |

Final scores after optimization and staging deploy:

These 2026-04-29 measurements predate the later episode-detail template change
that made the hero render the static Django Chat SVG logo even when
`Podcast.cover_image` is set. Re-run the episode-detail audits after deploying
that change before treating the episode-detail rows as current performance
evidence.

| Page | Mode | Performance | Accessibility | Best Practices | SEO | LCP | CLS | TBT |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `/` -> `/episodes/` | desktop | 100 | 100 | 100 | 100 | 0.5 s | 0 | 0 ms |
| `/` -> `/episodes/` | mobile | 98 | 100 | 100 | 100 | 2.4 s | 0.022 | 0 ms |
| `/episodes/` | desktop | 100 | 100 | 100 | 100 | 0.5 s | 0 | 0 ms |
| `/episodes/` | mobile | 98 | 100 | 100 | 100 | 2.3 s | 0.022 | 0 ms |
| `/episodes/django-tasks-jake-howard/` | desktop | 100 | 100 | 100 | 100 | 0.6 s | 0 | 10 ms |
| `/episodes/django-tasks-jake-howard/` | mobile | 98 | 100 | 100 | 100 | 2.2 s | 0.034 | 90 ms |
| `/episodes/feed/` | desktop | 100 | 100 | 100 | 100 | 0.3 s | 0.001 | 0 ms |
| `/episodes/feed/` | mobile | 100 | 100 | 100 | 100 | 1.3 s | 0.001 | 0 ms |

Current scores after the HTML-discoverable hero background deployed to staging:

Measured on 2026-05-19 with Lighthouse 13.3.0. Reports are in
`/tmp/django-chat-lighthouse-20260519/`.

| Page | Mode | Performance | Accessibility | Best Practices | SEO | FCP | LCP | CLS | TBT | Speed Index |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `/episodes/` | desktop | 98 | 100 | 100 | 100 | 0.3 s | 0.5 s | 0.083 | 0 ms | 0.4 s |
| `/episodes/` | mobile | 100 | 100 | 100 | 100 | 1.1 s | 1.4 s | 0.001 | 0 ms | 1.1 s |
| `/episodes/django-tasks-jake-howard/` | desktop | 100 | 100 | 100 | 100 | 0.3 s | 0.3 s | 0 | 0 ms | 0.4 s |
| `/episodes/django-tasks-jake-howard/` | mobile | 100 | 100 | 100 | 100 | 1.4 s | 1.4 s | 0 | 0 ms | 1.4 s |

The 2026-05-19 `/episodes/` mobile report confirms the hero background is now
the LCP node, is discoverable from the initial HTML, has `fetchpriority="high"`,
and requests the smaller `show-hero-bg.avif` asset. Desktop requests the 2x AVIF
variant under the current `sizes="100vw"` rule (the new-header migration on
2026-05-26 dropped the legacy `120vw` overshoot — the hero now fills the
section width via `object-fit: cover`).

Accessibility follow-up on 2026-05-29: the primary navigation's
`aria-current="page"` link state now uses a brighter green than the hover/focus
state so it keeps WCAG AA text contrast on both the desktop topbar surface and
the slightly lighter stacked mobile navigation background. The CSS template test
calculates that contrast directly; re-run Lighthouse after deployment before
recording new scores.

Current scores after CSS minification deployed to staging:

Measured on 2026-05-19 with Lighthouse 13.3.0. Reports are in
`/tmp/django-chat-lighthouse-20260519-post-minify/`.

| Page | Mode | Performance | Accessibility | Best Practices | SEO | FCP | LCP | CLS | TBT | Speed Index |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `/` -> `/episodes/` | desktop | 98 | 100 | 100 | 100 | 0.3 s | 0.5 s | 0.083 | 0 ms | 0.4 s |
| `/` -> `/episodes/` | mobile | 100 | 100 | 100 | 100 | 1.3 s | 1.5 s | 0.001 | 0 ms | 1.3 s |
| `/episodes/` | desktop | 99 | 100 | 100 | 100 | 0.3 s | 0.5 s | 0.082 | 0 ms | 0.3 s |
| `/episodes/` | mobile | 100 | 100 | 100 | 100 | 1.2 s | 1.5 s | 0.001 | 0 ms | 1.2 s |
| `/episodes/django-tasks-jake-howard/` | desktop | 100 | 100 | 100 | 100 | 0.3 s | 0.3 s | 0.013 | 0 ms | 0.3 s |
| `/episodes/django-tasks-jake-howard/` | mobile | 100 | 100 | 100 | 100 | 1.2 s | 1.4 s | 0 | 0 ms | 1.2 s |
| `/episodes/feed/` | desktop | 100 | 100 | 100 | 100 | 0.3 s | 0.3 s | 0 | 0 ms | 0.3 s |
| `/episodes/feed/` | mobile | 100 | 100 | 100 | 100 | 1.1 s | 1.1 s | 0 | 0 ms | 1.1 s |

The deployed hashed `site.css` transfer is about 11.4 KiB in the Lighthouse
network trace, and the unminified CSS and unused CSS audits now pass on all
measured pages. The RSS XML endpoints returned HTTP 200 and gzip-compressed GET
responses.

Current scores after `view-transitions.js` defer and the player-facade minifier
fix deployed to staging:

Measured on 2026-05-19 with Lighthouse 13.3.0. Reports are in
`/tmp/django-chat-lighthouse-20260519-post-defer-minifier/`.

| Page | Mode | Performance | Accessibility | Best Practices | SEO | FCP | LCP | CLS | TBT | Speed Index |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `/` -> `/episodes/` | desktop | 98 | 100 | 100 | 100 | 0.3 s | 0.5 s | 0.083 | 0 ms | 0.4 s |
| `/` -> `/episodes/` | mobile | 100 | 100 | 100 | 100 | 1.2 s | 1.7 s | 0.001 | 0 ms | 1.2 s |
| `/episodes/` | desktop | 98 | 100 | 100 | 100 | 0.3 s | 0.5 s | 0.083 | 0 ms | 0.3 s |
| `/episodes/` | mobile | 100 | 100 | 100 | 100 | 1.4 s | 1.7 s | 0.001 | 0 ms | 1.4 s |
| `/episodes/django-tasks-jake-howard/` | desktop | 100 | 100 | 100 | 100 | 0.2 s | 0.3 s | 0 | 0 ms | 0.3 s |
| `/episodes/django-tasks-jake-howard/` | mobile | 100 | 100 | 100 | 100 | 1.1 s | 1.2 s | 0 | 0 ms | 1.1 s |
| `/episodes/feed/` | desktop | 100 | 100 | 100 | 100 | 0.3 s | 0.3 s | 0 | 0 ms | 0.3 s |
| `/episodes/feed/` | mobile | 100 | 100 | 100 | 100 | 1.1 s | 1.1 s | 0 | 0 ms | 1.1 s |

The deployed render-blocking request table now lists only `site.css`; the
deferred `view-transitions.js` file is no longer render-blocking. A staging
browser probe on `/episodes/django-deployments-in-2025-eric-matthes/` confirmed
that the corrected minified player selector matches, the facade becomes
`opacity: 0` with `pointer-events: none`, and the initialized Podlove iframe
occupies the same slot instead of stacking below the facade.

Current scores after the custom-player cutover on staging:

Measured on 2026-06-11 with Lighthouse 13.4.0 and Chrome for Testing 149.
Reports are in `/tmp/django-chat-lighthouse-20260611/`.

| Page | Mode | Performance | Accessibility | Best Practices | SEO | FCP | LCP | CLS | TBT | Speed Index |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `/episodes/` | desktop | 100 | 100 | 100 | 100 | 0.3 s | 0.4 s | 0.01 | 0 ms | 0.6 s |
| `/episodes/` | mobile | 100 | 100 | 100 | 100 | 0.9 s | 1.2 s | 0.002 | 0 ms | 1.1 s |
| `/episodes/how-france-ditched-microsoft-samuel-paccoud/` | desktop | 99 | 100 | 100 | 100 | 0.7 s | 0.8 s | 0.015 | 0 ms | 0.8 s |
| `/episodes/how-france-ditched-microsoft-samuel-paccoud/` | mobile | 100 | 100 | 100 | 100 | 1.1 s | 1.1 s | 0.024 | 0 ms | 1.1 s |

The custom `cast-audio-player` did not regress any category: TBT stayed at
0 ms and CLS stayed near zero on both pages. The single sub-100 cell
(episode-detail desktop, 99) comes from two known small items: the
render-blocking `site.css` (~16 KiB transfer, est. 140 ms — the existing
split/critical-inline backlog decision) and the episode-detail LCP node being
the sidebar `img.show-artwork`, which is HTML-discoverable but lacks
`fetchpriority="high"`. At measurement time the episode-detail `<head>` still
inlined the Podlove critical-CLS height guard (`podlove-player { … }`), which
matched nothing after the cutover; the guard was removed with the rest of the
Podlove player path later the same day (see the backlog Done list below).

## Changes Required

The baseline was already strong for the subscribe page, but the episode index
and episode detail page needed small fixes:

- The episode index visible artwork uses local Django Chat assets instead of
  downloading the external Simplecast original. This reduced index payload from
  about 530 KiB to 190 KiB and improved mobile LCP. A later episode-detail
  template change also renders the static Django Chat SVG logo directly in the
  hero; that later change is not reflected in the 2026-04-29 table above.
- Artwork images now include stable `width` and `height`; the hero logo is
  marked `fetchpriority="high"` and `decoding="async"`.
- The episode filter date inputs now have explicit labels, fixing the
  Lighthouse accessibility failure on `/episodes/`.
- The Podlove player host element originally used a fixed, critical height
  reservation before the third-party player initialized: 302 px desktop and
  514 px mobile. The compact Django Chat player template now has its own
  shorter `podlove-player[data-template]` reservation, so the one-line-style
  player does not leave the old tall blank space while still guarding against
  layout shift. The base template also declares `data-theme="light"` so the
  player initializer does not request Podlove's dark color scheme on an
  otherwise light page.
- The compact player mobile reservation is kept in sync between the critical
  inline CSS and the site stylesheet so the show notes do not move when the
  player iframe is inserted.
- Public runtime CSS uses the smaller Roboto variable font for headings and
  episode-number badges instead of loading the larger Roboto Flex display font
  on Lighthouse-critical pages.
- Episode detail pages keep the Podlove player's click-to-load mode under the
  hood so the heavyweight embed script, player API response, and third-party
  player assets are requested only after user interaction. Django Chat renders
  its own lightweight player-shaped facade, keeps that footprint stable while
  the iframe initializes, and starts the player on hover, focus, tap, or button
  click.

## Performance Optimization Backlog

This section tracks follow-up performance work after the original 2026-04-29
host-review Lighthouse pass. Keep it focused on concrete findings from
Lighthouse, Playwright, or browser network probes.

Done:

- 2026-05-19: The `/episodes/` show-hero background moved from a CSS
  `image-set()` pseudo-element to an HTML-discoverable `<picture>` with AVIF,
  WebP, and JPEG fallbacks. The image is marked `fetchpriority="high"` and
  `decoding="async"`, and the sticky clipped media layer keeps the same visual
  behaviour as the old CSS background. A local mobile Playwright probe verified
  Chromium requests `show-hero-bg.avif` instead of the heavier
  `show-hero-bg@2x.avif`; a local mobile Lighthouse run reported
  `lcp-discovery-insight` score `1` with the hero image as the LCP node.
- 2026-05-19: Re-ran deployed staging Lighthouse after the hero-image deploy for
  `/episodes/` and `/episodes/django-tasks-jake-howard/` in desktop and mobile
  modes. Scores were 98-100 across all Lighthouse categories, and `/episodes/`
  mobile LCP dropped to 1.4 s.
- 2026-05-19: Re-checked the remaining render-blocking and CSS audits. The
  known render blockers are still the head-loaded `view-transitions.js` file
  (~5.5 KiB transfer) and shared `site.css` (~27.2 KiB transfer). Lighthouse
  reports 300 ms CSS render-blocking duration on mobile and a CSS minification
  opportunity of about 12 KiB transfer. A local esbuild minification probe
  reduced `site.css` from 105,869 bytes to 57,770 bytes raw, and from 27,167
  bytes to 11,364 bytes when gzipped.
- 2026-05-19: Added deploy-path CSS minification through
  `django_chat.core.staticfiles.MinifiedCompressedManifestStaticFilesStorage`.
  It minifies copied first-party `django_chat/css/*.css` files during
  `collectstatic`, before manifest hashing and WhiteNoise compression, so the
  source CSS stays readable and the deployment host does not need a frontend
  build toolchain. A full local `collectstatic` probe reduced the hashed
  deployed `site.css` to 58,471 bytes raw and 11,331 bytes gzipped. A deployed
  staging Lighthouse re-run confirmed about 11.4 KiB CSS transfer and 98-100
  scores across all measured categories.
- 2026-05-19: Deferred the head-loaded `view-transitions.js` file. Targeted
  browser checks still passed for enhanced filter controls and same-document
  filter transitions, a local Chromium timing probe confirmed the
  cross-document `pageswap` / `pagereveal` handlers still ran for transitions
  with `viewTransition`, and a local mobile Lighthouse run removed
  `view-transitions.js` from the render-blocking request table. A deployed
  staging Lighthouse re-run confirmed that only `site.css` remains in the
  render-blocking request table.
- 2026-05-19: Fixed a deploy-path CSS minifier bug that removed the descendant
  space from `podlove-player[data-django-chat-player-ready="true"]
  [data-django-chat-player-placeholder]`. The broken minified selector left
  the lightweight player facade visible above the initialized Podlove iframe on
  staging. A deployed staging browser probe confirmed the corrected minified
  selector matches and the facade hides when the Podlove iframe is ready.
- 2026-06-11: Removed the entire Podlove player path (loader script, facade
  markup and CSS layer, theme settings, template-proxy endpoint, deploy
  toggle) after the custom-player cutover, including the inline Podlove
  critical-CLS height guard whose `podlove-player` selectors no longer
  matched anything. The custom player is server-rendered, so no replacement
  CLS reserve is needed (measured CLS stayed near zero without it).
- 2026-06-11: Reverted the 2026-05-19 `view-transitions.js` defer. The deferred
  script registered its `pagereveal` listener only after the full document
  parse (readyState `interactive`), while the browser fires `pagereveal` at the
  first rendering opportunity — on staging the listener lost that race on
  every cross-document navigation (instrumented Chromium showed the event
  firing 13–160 ms before registration), so detail-to-overview navigations
  landed at the top without the reverse morph. The earlier local timing probe
  that justified the defer passed only because localhost wins the race. The
  file must stay a classic parser-blocking head script (~5.5 KiB transfer);
  a browser regression test now pins the registration to readyState
  `loading`. Do not re-defer; if its render-blocking cost ever matters,
  the only safe alternative is `async` plus `blocking="render"`, which still
  blocks first render by design.

Planned:

- 2026-06-11: Consider `fetchpriority="high"` on the episode-detail sidebar
  `img.show-artwork` — Lighthouse identifies it as the LCP node (discoverable,
  not priority-hinted). Worth at most ~1 desktop performance point.
- Split or critical-inline CSS for the public host-review pages only if the
  remaining CSS render-blocking estimate is worth the added complexity. The
  current single `site.css` keeps the system simple, and the unminified CSS and
  unused CSS audits pass after deploy-time minification.
- Revisit the `rel="expect" blocking="render"` hints on the index and detail
  pages after the image and script/CSS work. They improve native
  cross-document transition stability, but they should stay only if their
  visual benefit outweighs first-render cost.

## Caveats

The 2026-04-29 through 2026-05-19 Lighthouse reports measured the Podlove
player era (click-to-load facade keeping the third-party bundle off the
initial load). The 2026-06-11 reports are the first taken against the
django-cast custom player, which has since become the only player path.

The root URL intentionally redirects to `/episodes/`. Lighthouse records that
redirect but final root scores are still 98-100.
