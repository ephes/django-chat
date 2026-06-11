/* Episode hero separator handoff.
 *
 * The closed player region's short separator is anchored to the cover's
 * bottom edge via `min-height: var(--episode-cover-size)` on
 * `.episode-hero-content` — that only covers content *shorter* than the
 * cover. When the closed content column is taller (a three-line title plus
 * player and transcript header at narrow two-column widths), we mark the
 * hero with `data-hero-overflow` and the CSS hands off to the same
 * full-width hero rule the open-transcript state uses. CSS alone cannot
 * compare the two heights, hence this observer. Without JS the short line
 * simply sits below the cover (graceful fallback).
 *
 * IMPORTANT: the comparison must use the CLOSED extent of the content —
 * the bottom of the transcript toggle row, which sits above the expanding
 * panel body and therefore never moves while the fold animates. Measuring
 * live children bounds instead would flip the attribute mid-animation and
 * snap `min-height`/border/padding right as the close spring settles
 * (visible stutter).
 */
(() => {
  if (typeof ResizeObserver === "undefined") return;
  const hero = document.querySelector(".episode-hero");
  if (!hero) return;
  const content = hero.querySelector(".episode-hero-content");
  const cover = hero.querySelector(".episode-number-badge--detail");
  if (!content || !cover) return;

  // Bottom edge of the content's static parts: expanding panels
  // (.cast-panel) are represented by their toggle header, everything else
  // by its own box.
  const closedBottom = (root) => {
    let bottom = -Infinity;
    for (const child of root.children) {
      if (child.matches(".cast-panel")) {
        const toggle = child.querySelector(".cast-panel__toggle");
        if (toggle) bottom = Math.max(bottom, toggle.getBoundingClientRect().bottom);
        continue;
      }
      if (child.querySelector(".cast-panel")) {
        bottom = Math.max(bottom, closedBottom(child));
        continue;
      }
      bottom = Math.max(bottom, child.getBoundingClientRect().bottom);
    }
    return bottom;
  };

  let frame = 0;
  const update = () => {
    frame = 0;
    const coverRect = cover.getBoundingClientRect();
    const contentRect = content.getBoundingClientRect();
    // Only meaningful while cover and content sit side by side; in the
    // stacked mobile layout the content is always below the cover and the
    // anchor design does not apply.
    const sideBySide = contentRect.left >= coverRect.right;
    const overflows = sideBySide && closedBottom(content) - coverRect.bottom > 0.5;
    hero.toggleAttribute("data-hero-overflow", overflows);
  };
  const schedule = () => {
    if (!frame) frame = requestAnimationFrame(update);
  };
  new ResizeObserver(schedule).observe(content);
  window.addEventListener("resize", schedule);
  schedule();
})();
