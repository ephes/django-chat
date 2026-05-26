(() => {
  'use strict';
  const root = document.documentElement;
  const shell = document.querySelector('[data-show-hero-shell]');
  const brand = document.querySelector('[data-show-hero-brand]');
  const brandLogo = document.querySelector('[data-show-hero-brand-logo]');
  const brandName = document.querySelector('[data-show-hero-brand-name]');
  const heroLogo = document.querySelector('[data-show-hero-hero-logo]');
  const heroLogoImg = heroLogo && heroLogo.querySelector('img');
  const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const hasNativeTimeline =
    typeof CSS !== 'undefined' &&
    typeof CSS.supports === 'function' &&
    CSS.supports('animation-timeline', 'scroll(root block)');

  // ---- 1. Auto-fit ----
  // Measure the hero logo + the topbar brand slot and write the exact
  // blown-up start geometry of the flying logo into :root. Both the CSS
  // @supports path and the polyfill below read these vars so the morph
  // pixel-aligns with the hero logo at every viewport. Runs on every
  // hero page (subpages early-return on the heroLogo guard).
  if (heroLogo && brandLogo && heroLogoImg) {
    const fit = () => {
      // Drop the CSS animation AND the polyfill's inline transform for
      // the read so getBoundingClientRect() sees the brand at its
      // un-morphed natural slot. Without clearing the transform, a refit
      // mid-polyfill (font swap, ResizeObserver) would measure the
      // already-flying brand and rewrite the morph vars to near-identity,
      // collapsing the next scroll tick onto the docked position.
      // Preserve and restore both so the polyfill state survives the read.
      const prevAnim = brandLogo.style.animationName;
      const prevTransform = brandLogo.style.transform;
      brandLogo.style.animationName = 'none';
      brandLogo.style.transform = 'none';
      const b = brandLogo.getBoundingClientRect();
      brandLogo.style.transform = prevTransform;
      brandLogo.style.animationName = prevAnim;

      const h = heroLogoImg.getBoundingClientRect();
      if (!b.height || !h.height) return;

      // Brand is sticky-pinned at scroll-0; hero logo is in flow.
      // Normalise the hero rect to a scroll-0 document coord. Keyframe
      // origin is `left center` and translate runs before scale.
      const heroTop = h.top + window.scrollY;
      const scale = h.height / b.height;
      const tx = h.left - b.left;
      const ty = (heroTop + h.height / 2) - (b.top + b.height / 2);

      root.style.setProperty('--show-hero-morph-scale', scale.toFixed(4));
      root.style.setProperty('--show-hero-morph-tx', tx.toFixed(1) + 'px');
      root.style.setProperty('--show-hero-morph-ty', ty.toFixed(1) + 'px');
    };

    fit();
    addEventListener('load', fit);
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(fit);

    // ResizeObserver on the shell covers cqw-driven layout changes
    // (hero-logo resizes with the container) plus parent resizes that
    // wouldn't fire a window resize. heroLogoImg is observed directly to
    // catch font-load reflows of the bubble. brandLogo is NOT observed:
    // its height is static (`3rem` literal, no panel slider in prod), so
    // a watcher would never fire and only burns one ObserverEntry slot.
    // rAF-throttled to one fit per frame.
    let pending = false;
    const schedule = () => {
      if (pending) return;
      pending = true;
      requestAnimationFrame(() => { pending = false; fit(); });
    };
    const ro = new ResizeObserver(schedule);
    if (shell) ro.observe(shell);
    ro.observe(heroLogoImg);
  }

  // ---- 2. Scroll-morph polyfill ----
  // Drives the morph on browsers without native
  // `animation-timeline: scroll(root)` — mainly iOS Safari < 26. Reads
  // the same CSS vars as the @supports CSS block so timing + start
  // geometry stay consistent. No-ops when reduced-motion is on or
  // native scroll-driven animations are supported.
  if (!hasNativeTimeline && !reduced && brand && brandLogo && brandName && heroLogo) {
    // Mirror the @supports baseline: brand visible, hero logo hidden,
    // CSS keyframe animations off (the polyfill drives transform +
    // opacity directly). transform-origin: left center must match the
    // @supports rule so the auto-fit-measured offset + scale align the
    // flying logo with the hero logo at scroll=0.
    brand.style.visibility = 'visible';
    brand.style.pointerEvents = 'auto';
    heroLogo.style.visibility = 'hidden';
    brandLogo.style.animationName = 'none';
    brandName.style.animationName = 'none';
    brandLogo.style.transformOrigin = 'left center';

    const readPx = (name, fallbackPx) => {
      const v = getComputedStyle(root).getPropertyValue(name).trim();
      const n = parseFloat(v);
      return Number.isFinite(n) ? n : fallbackPx;
    };
    // Cubic ease-out — visual match for cubic-bezier(.2,.7,.2,1).
    const ease = t => 1 - Math.pow(1 - t, 3);
    const ramp = (s, a, b) => Math.min(Math.max((s - a) / Math.max(b - a, 1), 0), 1);

    const update = () => {
      const vh = innerHeight / 100;
      const mS = readPx('--show-hero-morph-start',      0)  * vh;
      const mE = readPx('--show-hero-morph-end',       30) * vh;
      const tS = readPx('--show-hero-morph-text-start', 25) * vh;
      const tE = readPx('--show-hero-morph-text-end',   32) * vh;
      const s = scrollY;
      const p = ease(ramp(s, mS, mE));
      const q = ease(ramp(s, tS, tE));

      const scale0 = readPx('--show-hero-morph-scale', 5.8);
      const tx0    = readPx('--show-hero-morph-tx',    0);
      const ty0    = readPx('--show-hero-morph-ty',    0);
      const cs = scale0 + (1 - scale0) * p;
      const cx = tx0    + (0 - tx0)    * p;
      const cy = ty0    + (0 - ty0)    * p;
      brandLogo.style.transform = `translate(${cx}px, ${cy}px) scale(${cs})`;

      brandName.style.opacity = q;
      brandName.style.transform = `translateX(${-0.6 * (1 - q)}rem)`;
    };

    let rafId = 0;
    const schedule = () => {
      if (rafId) return;
      rafId = requestAnimationFrame(() => { rafId = 0; update(); });
    };
    addEventListener('scroll', schedule, { passive: true });
    addEventListener('resize', schedule);
    // Wait one frame so auto-fit writes --show-hero-morph-* first.
    requestAnimationFrame(update);
  }

  // ---- 3. Parallax ----
  // Headphones + LISTEN UP fill/outline drift in different directions
  // so the three layers never sit aligned. Mouse on fine pointer,
  // scroll on touch. Writes 6 CSS vars on the shell (NOT :root) so the
  // per-frame style invalidation stays scoped to the hero subtree
  // instead of bouncing through the whole document. rAF lerp toward
  // target for smooth motion. Skips on reduced-motion and on pages
  // without the hero.
  if (!reduced && shell) {
    // Per-layer magnitudes in cqw (container-width-relative, matches
    // the rest of the hero's sizing). Headphones move in lockstep with
    // the outline (treated as one composite "outline + headphones");
    // fill drifts mirrored against them. Tuned subtle on purpose — the
    // split between fill and outline still reads as drift apart, but
    // the absolute travel stays small enough not to compete with the
    // bubble + logo as the eye-catch.
    const M = {
      hp:      { x: -0.4, y: -0.25 },
      outline: { x: -0.4, y: -0.25 },
      fill:    { x:  0.4, y:  0.25 },
    };

    // Target (tx,ty) set by the input handler; current (cx,cy) lerped
    // toward target each tick. Both in -1..+1 range.
    let tx = 0, ty = 0, cx = 0, cy = 0;
    let running = false;

    const apply = () => {
      const set = (name, v) => shell.style.setProperty(name, v.toFixed(3) + 'cqw');
      set('--show-hero-px-hp-x',      cx * M.hp.x);
      set('--show-hero-px-hp-y',      cy * M.hp.y);
      set('--show-hero-px-outline-x', cx * M.outline.x);
      set('--show-hero-px-outline-y', cy * M.outline.y);
      set('--show-hero-px-fill-x',    cx * M.fill.x);
      set('--show-hero-px-fill-y',    cy * M.fill.y);
    };

    const tick = () => {
      cx += (tx - cx) * 0.08;
      cy += (ty - cy) * 0.08;
      apply();
      if (Math.abs(tx - cx) > 0.001 || Math.abs(ty - cy) > 0.001) {
        requestAnimationFrame(tick);
      } else {
        cx = tx; cy = ty; apply();
        running = false;
      }
    };
    const start = () => {
      if (!running) { running = true; requestAnimationFrame(tick); }
    };

    const clamp1 = v => Math.max(-1, Math.min(1, v));
    const finePointer = matchMedia('(hover: hover) and (pointer: fine)').matches;

    if (finePointer) {
      shell.addEventListener('pointermove', (e) => {
        const r = shell.getBoundingClientRect();
        tx = clamp1((e.clientX - r.left - r.width  / 2) / (r.width  / 2));
        ty = clamp1((e.clientY - r.top  - r.height / 2) / (r.height / 2));
        start();
      });
      shell.addEventListener('pointerleave', () => { tx = 0; ty = 0; start(); });
    } else {
      // Coarse pointer / touch: scroll-linked Y drift. Maps the first
      // ~0.8 viewport-heights of scroll to 0..+1 so each layer drifts
      // in its own magnitude direction. X stays at rest.
      const onScroll = () => {
        ty = Math.min(1, scrollY / Math.max(innerHeight * 0.8, 1));
        tx = 0;
        start();
      };
      addEventListener('scroll', onScroll, { passive: true });
      onScroll();
    }
  }
})();
