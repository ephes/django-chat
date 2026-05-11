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

## Prototype Update: Pagination Pivot

The first implementation pass confirmed that native cross-document transitions
work well for episode overview/detail navigation, especially with shared title
and episode-number badge elements. Pagination was different: even with
`ViewTransition.types`, browser behavior felt like a fast full-page top/down
navigation rather than a stable result-list change.

For the prototype, pagination therefore switched to a same-document progressive
enhancement while keeping normal server-rendered pagination links as the
fallback:

- Intercept plain same-origin pagination clicks only when
  `document.startViewTransition()` is available and reduced motion is not
  requested.
- Keep filter/search form submissions and filter-clear links on native
  cross-document navigation. The same-document interception path made the search
  transition easy to miss, while the original MPA path gives the
  `pageswap`/`pagereveal` filter transition a stable lifecycle.
- For pagination, fetch the next full server-rendered page, parse it with
  `DOMParser`, and swap the filter form plus the `.episode-results` container
  inside `document.startViewTransition()`.
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
