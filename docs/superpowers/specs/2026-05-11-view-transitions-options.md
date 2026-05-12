# View Transitions Options

Research and implementation options for adding page and result transitions to
the Django Chat episode experience.

## Context

Django Chat is currently a server-rendered Django/Wagtail/django-cast
multi-page app. The relevant surfaces are:

- Episode overview: `django_chat/templates/cast/django_chat/blog_list_of_posts.html`
- Episode detail: `django_chat/templates/cast/django_chat/episode.html`
- Pagination: `django_chat/templates/cast/django_chat/pagination.html`
- Filter/search form: `django_chat/templates/cast/django_chat/_filter_form.html`
- Site CSS: `django_chat/static/django_chat/css/site.css`

The current markup already has useful hooks: `.episode-row`,
`.episode-number-badge`, `.episode-list`, `.filter-form`, `.pagination-nav`,
`.episode-detail`, `.episode-hero`, and `.back-link`.

## Research Notes

- Bramus's MPA update is directly relevant: cross-document transitions for
  normal websites now opt in with CSS:
  `@view-transition { navigation: auto; }`. The old meta-tag opt-in should not
  be used. Source:
  https://www.bram.us/2024/05/24/cross-document-view-transitions-for-mpa-you-need-view-transition-to-opt-in-not-the-meta-tag/
- Chrome's cross-document guide says MPA transitions are same-origin only, need
  opt-in on both pages, and are triggered by normal same-origin navigation
  rather than `document.startViewTransition()`. Source:
  https://developer.chrome.com/docs/web-platform/view-transitions/cross-document
- The same guide documents `pageswap` and `pagereveal` for just-in-time
  customization, plus `ViewTransition.types` for cases such as pagination
  forward/backward transitions. Source:
  https://developer.chrome.com/docs/web-platform/view-transitions/cross-document
- MDN documents `document.startViewTransition()` as the same-document API. It is
  useful when JavaScript mutates the DOM, but it is not the primary path for
  normal MPA navigation. Source:
  https://developer.mozilla.org/en-US/docs/Web/API/Document/startViewTransition
- htmx supports View Transitions for swaps with `hx-swap="... transition:true"`.
  This is useful for partial updates, but it also means owning boosted history,
  partial response shape, and script lifecycle. Source:
  https://htmx.org/essays/view-transitions/
- Bramus's later nested/scoped transition work is interesting for clipping and
  independently interactive subtrees, but it depends on newer browser support
  and is not the right first prototype target for this site. Sources:
  https://www.bram.us/2025/09/24/nested-view-transition-groups/ and
  https://developer.chrome.com/docs/css-ui/view-transitions/element-scoped-view-transitions

## Recommendation

Start with native cross-document View Transitions plus a very small classic
head script. Do not introduce htmx for the first prototype.

This fits the current architecture: the pages are already server-rendered,
same-origin, and have normal links/forms. The prototype can be a progressive
enhancement: unsupported browsers keep the current hard navigation, and users
with reduced-motion preferences get no transition.

Use htmx only if the native MPA path cannot make the search/filter experience
feel good enough, or if we later decide that search results should update
without a full document load.

## Prototype Update: Index Navigation Pivot

The first implementation pass confirmed that native cross-document transitions
work well for episode overview/detail navigation, especially with shared title
and episode-number badge elements. Pagination was different: even with
`ViewTransition.types`, browser behavior felt like a fast full-page top/down
navigation rather than a stable result-list change. Native cross-document
search transitions also reset the next page to the top, putting the animated
result list below the first viewport on the first search.

For the prototype, index navigation therefore switched to a same-document
progressive enhancement while keeping normal server-rendered links/forms as the
fallback:

- Intercept plain same-origin pagination clicks only when
  `document.startViewTransition()` is available and reduced motion is not
  requested.
- Intercept filter/search form submissions and filter-clear links under the
  same conditions. Native cross-document search transitions reset the next page
  to the top, which puts the animated result list below the first viewport on
  the first search.
- For pagination and filter/search, start `document.startViewTransition()`
  immediately, fetch the next full server-rendered page inside its update
  callback, parse it with `DOMParser`, and swap the filter form plus the
  `.episode-results` container.
- Update the URL with `history.pushState()` and handle pagination
  back/forward with the same index-page swap.
- Keep this dependency-free. This is intentionally not htmx and does not add a
  partial-template response mode yet.
- Sync basic head metadata for the soft pagination URL and move focus into the
  updated results region so the same-document swap behaves more like navigation.

The pagination animation is intentionally slower than the original guardrail
while the prototype is being judged visually: the current result-list crossfade
uses roughly 820ms out and 940ms in. Tighten this before production if it feels
too slow after visual iteration.

Because the fetch runs inside the same-document transition update callback, a
slow response can make the old result-list snapshot appear frozen until the
replacement HTML arrives. Keep the hard-navigation fallback for unsupported or
reduced-motion contexts, and consider a timeout fallback if the prototype ever
feels stuck on slower networks.

The detail page "Back to Episodes" link is also progressively adjusted from
the remembered episode-row click URL, so an episode opened from page 2 can
return to `/episodes/?page=2` and still use the shared detail-to-overview
transition. Without JavaScript or storage, the static fallback remains
`/episodes/`.

The index and detail templates add `rel="expect"` render-blocking hints for
their main content elements. These hints give native cross-document transitions
a stable first paint target before snapshots are finalized, reducing the chance
of a skipped or visually empty first overview/detail transition after reload.

The current helper deliberately gates on the Navigation API plus
`pageswap`/`pagereveal`, which keeps this prototype conservative and
Chrome-focused. Browsers without that combination fall back to normal
server-rendered navigation.

## Option A: Native MPA View Transitions

Summary: Add CSS opt-in, CSS animations, and a tiny script that sets transition
types and temporary element names during navigation.

Implementation shape:

- Add `@view-transition { navigation: auto; }` to `site.css`.
- Add transition CSS under `@media (prefers-reduced-motion: no-preference)`.
- Add a classic parser-blocking script in `base.html` before first render for
  `pagereveal`. Keep it small; load any non-critical helpers later if needed.
- Add stable data attributes to episode links, for example
  `data-vt-episode-slug="{{ post.slug }}"`.
- On overview-to-detail navigation, set a temporary `view-transition-name` on
  the clicked `.episode-row` and/or `.episode-number-badge`, then match it on
  the detail page title or hero area.
- On detail-to-overview navigation, only animate a shared element when the
  destination overview contains that episode row. Otherwise fall back to a
  content fade/slide.
- For pagination, derive `forwards` or `backwards` from the old and new `page`
  query parameter, then animate `.episode-list` and `.pagination-nav`.
- For search/filter submissions, use a `filter` transition type. Keep the
  filter form visually stable and animate only the result list.

Pros:

- Minimal dependency and minimal architectural change.
- Keeps Django templates and normal links/forms as the source of truth.
- Works as progressive enhancement with clean fallback.
- Best fit for overview/detail and pagination because those are full-page MPA
  navigations today.

Cons:

- Browser support is still uneven for some advanced pieces, especially newer
  scoped/nested features.
- Direction and shared-element matching need careful cleanup for BFCache.
- Search result transitions may be less controllable than a same-document
  partial swap.

Best prototype scope:

1. Simple root/content fade for all same-origin navigations.
2. Pagination slide left/right based on `?page=`.
3. Search/filter result-list fade/slide while the form remains stable.
4. One shared element between list and detail, likely the episode number badge
   or title, not the Podlove player.

## Option B: htmx Partial Swaps With View Transitions

Summary: Add htmx to the episode index only, make search and pagination fetch
partial HTML, push the URL, and use `hx-swap` with `transition:true`.

Implementation shape:

- Introduce htmx on the overview page.
- Wrap the filter form, list, empty state, and pagination in one stable
  container, for example `#episode-results`.
- Make the filter form and pagination links target that container.
- Use `hx-push-url="true"` so the browser URL remains shareable.
- Render the same server-side template for full page requests and a partial
  template for htmx requests.
- Use `document.startViewTransition()` indirectly through htmx's swap support.

Pros:

- More control for search/filter result changes.
- Avoids full document reload for repeated filtering and pagination.
- Can feel more app-like while still using server-rendered HTML.

Cons:

- Adds a dependency and a second response mode to maintain.
- Needs careful testing for history restore, focus, scroll, no-results state,
  canonical URLs, and analytics.
- Does not help overview-to-detail transitions as directly unless links are
  boosted too, which increases lifecycle risk around Podlove and page scripts.

Best prototype scope:

- Search/filter and pagination only. Leave overview/detail as native MPA
  navigation until the partial-swap lifecycle is proven.

## Option C: CSS-Only Page Load Animations

Summary: Add tasteful entry animations to result rows and detail content on
page load, with no View Transition API.

Pros:

- Lowest complexity and broadest compatibility.
- No browser snapshot behavior, no BFCache cleanup, no script lifecycle.

Cons:

- No true shared-element transition from overview to detail.
- Pagination direction is hard to express.
- Can feel like decoration rather than preserving navigation context.

This is useful as a fallback style layer but is not enough for the requested
"overview to detail and back" effect.

## Option D: SPA/Router Library

Summary: Introduce a client-side navigation layer such as Swup/Turbo-style
page replacement or a custom router.

Pros:

- Maximum control over transitions.

Cons:

- Poor fit for this project right now.
- Higher risk around Wagtail/django-cast templates, Podlove player lifecycle,
  metadata, feeds, and accessibility.

Do not use this for the prototype.

## Future Option: Persistent Audio Player

The current View Transitions work can make episode navigation feel smoother, but
it cannot keep audio alive through normal MPA navigation. A cross-document view
transition snapshots the old and new documents around a same-origin navigation;
the old document, including the Podlove iframe/audio state, is still replaced.
That means a Simplecast-style stable player needs a client-side navigation
layer or another persistent shell, not just native MPA View Transitions.

This is a possible future enhancement for
`https://djangochat.staging.django-cast.com/episodes/`, especially if we want a
player that starts on an episode detail page and keeps playing while the user
returns to the episode index or opens another episode.

Preferred future direction:

- Add a small client-side navigation layer for the episode index and episode
  detail pages.
- Keep one global mini-player in `base.html`, outside the content region that
  gets swapped during navigation.
- Prefer a custom HTML audio mini-player for the persistent surface, using the
  imported MP3 URL and episode metadata, rather than trying to preserve the
  full Podlove iframe as the long-lived player.
- Keep the rich Podlove player on episode detail pages until the persistent
  player is proven. Later, decide whether the detail-page player should hand off
  to the global player or become a secondary rich view of the same audio state.
- Treat playback start as user-gesture-driven. Browser autoplay policies still
  apply; the persistent player solves "continue playback while navigating", not
  "start audible playback automatically on a fresh page load".

Implementation options:

- Turbo Drive plus a `data-turbo-permanent` global player is the strongest fit.
  Turbo keeps the browser document alive and can preserve marked elements across
  visits while the server remains the source of HTML. This would be the closest
  route to a Simplecast-like feel without rebuilding the site as a full SPA.
- A custom PJAX/navigation layer could build on the existing
  `view-transitions.js` direction and avoid a dependency, but we would own body
  swapping, head metadata syncing, script lifecycle, history, scroll/focus,
  analytics hooks, error fallback, and Podlove cleanup.
- htmx `hx-boost` can progressively enhance normal links/forms, but its
  preservation model is less attractive for this case because the current player
  is iframe-based. If htmx is used, prefer preserving a custom global audio
  element rather than the Podlove iframe.
- swup or Barba-style libraries are viable but more animation/router oriented
  than this project needs for a first persistent-player pass.
- An iframe app shell would preserve playback but is a poor fit for URL,
  accessibility, SEO, and deep-link behavior.

Rough effort:

- Prototype: 1-2 days for Turbo Drive plus a simple persistent `<audio>`
  mini-player on episode/index navigation.
- Production-ready version: 4-8 days after prototype, mostly browser testing,
  history/scroll/focus behavior, metadata/head updates, no-JavaScript fallback,
  and django-cast/Podlove script lifecycle checks.
- Full Simplecast-like polish: 1-2+ weeks if it includes queueing, expanded and
  collapsed player states, Media Session controls, mobile bottom-bar behavior,
  handoff from detail players, and visual transition tuning.

Useful references:

- Chrome cross-document View Transitions:
  https://developer.chrome.com/docs/web-platform/view-transitions/cross-document
- Turbo permanent elements:
  https://turbo.hotwired.dev/handbook/building
- htmx boosted navigation:
  https://htmx.org/attributes/hx-boost/
- htmx preserved elements:
  https://htmx.org/attributes/hx-preserve/
- Media Session API:
  https://developer.mozilla.org/en-US/docs/Web/API/MediaSession
- Chrome autoplay policy:
  https://developer.chrome.com/blog/autoplay

## Design Guardrails

- Respect `prefers-reduced-motion: reduce`.
- Keep animations short: roughly 160-240ms for fades, 220-320ms for slides.
  During prototype tuning, pagination may temporarily exceed this budget so the
  motion is easy to judge.
- Do not animate the Podlove iframe/player itself. It is heavy and can produce
  awkward snapshots.
- Do not animate the whole page chrome for pagination/search. Header and footer
  should stay visually stable.
- Avoid large-distance page slides on desktop; subtle movement is enough.
- Clean up temporary `view-transition-name` values after `ready` or `finished`.
- Ensure each active `view-transition-name` is unique in the old and new DOM.
- Treat all transitions as optional. The site must behave correctly without
  them.

## Prototype Plan

Use Option A first.

1. Add `django_chat/static/django_chat/js/view-transitions.js` and load it from
   `base.html` as a classic script in the head. Keep it dependency-free.
2. Add CSS opt-in and base transition keyframes in `site.css`.
3. Add data attributes to episode rows and pagination links so the script does
   not need brittle URL parsing for every case.
4. Implement pagination transition types first. This is the easiest behavior to
   judge visually.
5. Implement filter/search result transitions second.
6. Implement one shared list/detail transition last, after the basic timing
   feels right.

Suggested file ownership for a prototype agent:

- `django_chat/templates/cast/django_chat/base.html`
- `django_chat/templates/cast/django_chat/blog_list_of_posts.html`
- `django_chat/templates/cast/django_chat/episode.html`
- `django_chat/templates/cast/django_chat/pagination.html`
- `django_chat/static/django_chat/css/site.css`
- `django_chat/static/django_chat/js/view-transitions.js`
- focused tests under `django_chat/core/tests/` that assert the script is
  included and the expected data attributes/classes are rendered

## Acceptance Checks

- `just test`
- `prek run --all-files`
- Manual smoke in a View Transitions-capable browser:
  - `/episodes/` to an episode detail page and back.
  - `/episodes/?page=2` newer/older transitions with forced small page size or
    full catalog data.
  - `/episodes/?search=django` and clearing filters.
  - Browser back/forward across those states.
  - Reduced motion enabled at OS/browser level.
- Manual smoke in a browser without the relevant support, or with the script
  disabled, to confirm normal navigation still works.

## Refactor Criteria

After the prototype looks good on the dev server, refactor only the pieces that
proved useful:

- Keep the public CSS class names stable.
- Move URL/type derivation into small named functions with tests where practical.
- Remove any prototype-only animation types that did not earn their keep.
- Keep htmx out unless the prototype shows native MPA transitions cannot handle
  search/filter results well enough.
