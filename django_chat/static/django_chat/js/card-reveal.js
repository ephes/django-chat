(() => {
  'use strict';
  const root = document.documentElement;

  // Decorative reveal only — bail to the static resting layout when the user
  // prefers reduced motion or the browser lacks IntersectionObserver.
  if (matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  if (!('IntersectionObserver' in window)) return;

  // `.audio-feed` ("Latest entries" on the subscribe page) is deliberately
  // excluded: it renders as a borderless list row, not a card, so a rise-in
  // reads as content floating on nothing.
  const items = document.querySelectorAll(
    '.sponsor-slot, .sponsor-tier, .sponsor-callout, .subscribe-feature, .subscribe-why'
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

  // The stagger gap *before* an element (i.e. how long it lags the previous
  // card in the same entering batch). Defaults to STEP; an element can opt into
  // a more pronounced lag with `data-reveal-step="<ms>"` (e.g. the subscribe
  // "Why RSS?" box trails the MP3 card by two steps). Always 0 on phones, where
  // STEP is 0 and the cards enter one-at-a-time anyway.
  const gapBefore = (el) => {
    if (STEP === 0) return 0;
    const v = parseInt(el.dataset.revealStep, 10);
    return Number.isFinite(v) ? v : STEP;
  };

  // Two-observer hysteresis. The reveal animation translates a card 2rem
  // (≈32px) upward; an IntersectionObserver measures the *post-transform* rect,
  // so a single trigger band let the rise push the card back out of the band →
  // sink → rise → … the back-and-forth wobble when a card came to rest on the
  // band edge. Splitting the trigger into an inner reveal band (middle ~60%)
  // and a wider reset band (middle ~90%) leaves a hysteresis gap of ≥15% of the
  // viewport on each side — far larger than the 32px rise — so a revealed
  // card's own upward travel can never reach the reset boundary. The loop is
  // broken by geometry, not by timing guards. Replay survives: a card resets
  // and re-arms only once it genuinely leaves the wider band.

  // Reveal: rise (cascaded in document order) when entering the inner band.
  const revealIO = new IntersectionObserver((entries) => {
    const entering = entries
      .filter((e) => e.isIntersecting)
      .map((e) => e.target)
      .sort((a, b) =>
        a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING ? -1 : 1
      );
    let delay = 0;
    entering.forEach((el, i) => {
      if (i > 0) delay += gapBefore(el);
      clearTimeout(timers.get(el));
      timers.set(el, setTimeout(() => el.classList.add('is-in-view'), delay));
    });
  }, { threshold: 0, rootMargin: '-20% 0px -20% 0px' });

  // Reset: sink back (and re-arm) only once the card leaves the wider band.
  // Cancels any pending reveal so a card scrolled straight through never flashes.
  const resetIO = new IntersectionObserver((entries) => {
    for (const entry of entries) {
      if (!entry.isIntersecting) {
        clearTimeout(timers.get(entry.target));
        entry.target.classList.remove('is-in-view');
      }
    }
  }, { threshold: 0, rootMargin: '-5% 0px -5% 0px' });

  // Wire the observers up a beat after load so the cascade of the cards already
  // in the band starts a moment later, not on the first frame — on a large
  // screen the whole page is visible without scrolling, so an instant reveal
  // can't be perceived.
  const STARTUP_DELAY = 450;
  setTimeout(() => items.forEach((el) => {
    revealIO.observe(el);
    resetIO.observe(el);
  }), STARTUP_DELAY);
})();
