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

## Caveats

The 2026-04-29 Lighthouse reports predate the click-to-load player facade.
Subsequent browser network checks confirm that the third-party Podlove web
player bundle is not requested on initial episode detail page load; it is loaded
after the user hovers, focuses, taps, or clicks the player facade.

The root URL intentionally redirects to `/episodes/`. Lighthouse records that
redirect but final root scores are still 98-100.
