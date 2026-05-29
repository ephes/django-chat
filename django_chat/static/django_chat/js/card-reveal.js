(() => {
  'use strict';
  const root = document.documentElement;

  // Decorative reveal only — bail to the static resting layout when the user
  // prefers reduced motion or the browser lacks IntersectionObserver.
  if (matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  if (!('IntersectionObserver' in window)) return;

  const items = document.querySelectorAll(
    '.sponsor-slot, .sponsor-tier, .sponsor-callout, .subscribe-feature, .audio-feed'
  );
  if (!items.length) return;

  // The inline head script normally sets this pre-paint (so the start offset is
  // applied without a flash); set it here too in case that script was stripped.
  root.classList.add('js-reveal');

  // Subtle cascade: the cards entering together rise one shortly after another
  // in document order. The step is small relative to the rise, so the motions
  // overlap into a flowing wave rather than discrete hops. Only on big screens,
  // where the whole page is visible at once and there's something to cascade; on
  // phones the cards enter one-at-a-time while scrolling anyway.
  const STEP = matchMedia('(min-width: 64em)').matches ? 70 : 0;
  const timers = new WeakMap();

  // Reveal/reset are keyed to a central band, not the full viewport: a card
  // rises when it scrolls into the middle ~60% and sinks back when it leaves
  // that band. Re-arming on the band (rather than only once the card is fully
  // off-screen) is what lets the cards near the top of the page replay every
  // time you scroll past them — they rarely leave the viewport completely. The
  // sink is animated (see CSS), so leaving the band reads as a gentle settle,
  // not a hard snap.
  const io = new IntersectionObserver((entries) => {
    // Reset the cards leaving the band immediately (cancelling any pending
    // reveal) so they're armed to rise again on re-entry.
    for (const entry of entries) {
      if (!entry.isIntersecting) {
        clearTimeout(timers.get(entry.target));
        entry.target.classList.remove('is-in-view');
      }
    }
    // Cascade the cards entering the band in this notification, in doc order.
    const entering = entries
      .filter((e) => e.isIntersecting)
      .map((e) => e.target)
      .sort((a, b) =>
        a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING ? -1 : 1
      );
    entering.forEach((el, i) => {
      clearTimeout(timers.get(el));
      timers.set(el, setTimeout(() => el.classList.add('is-in-view'), i * STEP));
    });
  }, { threshold: 0, rootMargin: '-20% 0px -20% 0px' });

  // Wire the observer up a beat after load so the cascade of the cards already
  // in the band starts a moment later, not on the first frame — on a large
  // screen the whole page is visible without scrolling, so an instant reveal
  // can't be perceived.
  const STARTUP_DELAY = 450;
  setTimeout(() => items.forEach((el) => io.observe(el)), STARTUP_DELAY);
})();
