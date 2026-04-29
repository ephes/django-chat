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

- Visible show artwork now uses the copied Wagtail `Podcast.cover_image`
  renditions (`fill-560x560` for hero artwork, `fill-72x72` for the brand mark)
  instead of downloading the external Simplecast original. This reduced index
  payload from about 530 KiB to 190 KiB and improved mobile LCP.
- Artwork images now include stable `width` and `height`; hero artwork is
  marked `fetchpriority="high"` and `decoding="async"`.
- The episode filter date inputs now have explicit labels, fixing the
  Lighthouse accessibility failure on `/episodes/`.
- The Podlove player host element now has a fixed, critical height reservation
  before the third-party player initializes: 302 px desktop and 514 px mobile.
  This removed the large episode-detail CLS caused by show notes moving while
  the player rendered.

## Caveats

Lighthouse still reports unused CSS and JavaScript on the episode detail page
from the third-party Podlove web player bundle loaded from `cdn.podlove.org`.
That code is required for the interactive player and remains lazy/deferred
outside the first paint path. The final performance scores are still near 100,
so no further player replacement or redesign is part of the host-review gate.

The root URL intentionally redirects to `/episodes/`. Lighthouse records that
redirect but final root scores are still 98-100.
