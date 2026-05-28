(() => {
  'use strict';
  const root = document.documentElement;
  const shell = document.querySelector('[data-show-hero-shell]');
  const brand = document.querySelector('[data-show-hero-brand]');
  const brandLogo = document.querySelector('[data-show-hero-brand-logo]');
  const brandFly = document.querySelector('[data-show-hero-brand-fly]');
  const brandName = document.querySelector('[data-show-hero-brand-name]');
  const heroLogo = document.querySelector('[data-show-hero-hero-logo]');
  const heroLogoImg = heroLogo && heroLogo.querySelector('img');
  const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const hasNativeTimeline =
    typeof CSS !== 'undefined' &&
    typeof CSS.supports === 'function' &&
    CSS.supports('animation-timeline', 'scroll(root block)');

  // ---- 1. Auto-fit ----
  // Measure the crisp fly-twin's natural (render-size) box, the hero logo,
  // and the docked mark's slot, then write the flight's two endpoints into
  // :root: `from` overlays the hero logo (the twin scaled DOWN to match),
  // `to` overlays the docked mark. Both the CSS @supports path and the
  // polyfill below read these so the flight pixel-aligns at every viewport.
  // Runs on every hero page (subpages early-return on the heroLogo guard).
  if (heroLogo && brandLogo && brandFly && heroLogoImg) {
    const fit = () => {
      // Drop the fly's flight transform for the read so getBoundingClientRect()
      // sees its un-morphed natural box. Preserve/restore so a refit mid-flight
      // (font swap, ResizeObserver) doesn't measure the already-flying twin.
      const prevAnim = brandFly.style.animationName;
      const prevTransform = brandFly.style.transform;
      brandFly.style.animationName = 'none';
      brandFly.style.transform = 'none';
      // Batch all layout reads together so they share one forced reflow.
      const f = brandFly.getBoundingClientRect();   // fly twin, render size
      const b = brandLogo.getBoundingClientRect();  // docked mark slot
      const h = heroLogoImg.getBoundingClientRect(); // hero logo (offset-path)
      const sy = window.scrollY;
      brandFly.style.transform = prevTransform;
      brandFly.style.animationName = prevAnim;

      if (!f.height || !h.height || !b.height) return;

      // Fly twin is sticky-pinned at scroll-0; hero logo is in flow — normalise
      // its rect to a scroll-0 doc coord. Origin is `left center`, so align
      // left edges (x) and vertical centres (y); scale is the height ratio.
      const heroTop = h.top + sy;
      const fromScale = h.height / f.height;
      const fromTx = h.left - f.left;
      const fromTy = (heroTop + h.height / 2) - (f.top + f.height / 2);
      const toScale = b.height / f.height;
      const toTx = b.left - f.left;
      const toTy = (b.top + b.height / 2) - (f.top + f.height / 2);

      root.style.setProperty('--show-hero-fly-from-scale', fromScale.toFixed(4));
      root.style.setProperty('--show-hero-fly-from-tx', fromTx.toFixed(1) + 'px');
      root.style.setProperty('--show-hero-fly-from-ty', fromTy.toFixed(1) + 'px');
      root.style.setProperty('--show-hero-fly-to-scale', toScale.toFixed(4));
      root.style.setProperty('--show-hero-fly-to-tx', toTx.toFixed(1) + 'px');
      root.style.setProperty('--show-hero-fly-to-ty', toTy.toFixed(1) + 'px');
    };

    fit();
    addEventListener('load', fit);
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(fit);

    // ResizeObserver on the shell covers cqw-driven layout changes (hero logo
    // + docked mark resize with the container) plus parent resizes that
    // wouldn't fire a window resize. heroLogoImg is observed directly to catch
    // font-load reflows. rAF-throttled to one fit per frame.
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
  // Drives the flight on browsers without native
  // `animation-timeline: scroll(root)` — mainly iOS Safari < 26. Reads the
  // same CSS vars as the @supports block. Activates the fly twin inline (the
  // @supports layout rules didn't apply here) and drives its transform plus
  // the fly-out / dock-in opacity hand-off. No-ops under reduced-motion or
  // when native scroll-driven animations are supported.
  if (!hasNativeTimeline && !reduced && brand && brandLogo && brandFly && brandName && heroLogo) {
    brand.style.visibility = 'visible';
    brand.style.pointerEvents = 'auto';
    heroLogo.style.visibility = 'hidden';
    brandName.style.animationName = 'none';
    // Mirror the @supports fly-twin layout (absolute, render-tall, centred).
    Object.assign(brandFly.style, {
      display: 'block',
      position: 'absolute',
      left: '0',
      top: '50%',
      height: 'var(--show-hero-brand-render-h, 18rem)',
      marginTop: 'calc(var(--show-hero-brand-render-h, 18rem) / -2)',
      width: 'auto',
      transformOrigin: 'left center',
      pointerEvents: 'none',
      zIndex: '61',
    });
    // Mark starts hidden; the hand-off fades it in as the twin fades out.
    brandLogo.style.opacity = '0';

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
      const mS = readPx('--show-hero-morph-start',       0) * vh;
      const mE = readPx('--show-hero-morph-end',        30) * vh;
      const dS = readPx('--show-hero-morph-dock-start', 27) * vh;
      const tS = readPx('--show-hero-morph-text-start', 25) * vh;
      const tE = readPx('--show-hero-morph-text-end',   32) * vh;
      const s = scrollY;
      const p = ease(ramp(s, mS, mE));   // flight progress
      const d = ramp(s, dS, mE);         // hand-off progress (linear)
      const q = ease(ramp(s, tS, tE));   // brand-name progress

      const fS = readPx('--show-hero-fly-from-scale', 1);
      const fTx = readPx('--show-hero-fly-from-tx', 0);
      const fTy = readPx('--show-hero-fly-from-ty', 0);
      const tScale = readPx('--show-hero-fly-to-scale', 0.16);
      const tTx = readPx('--show-hero-fly-to-tx', 0);
      const tTy = readPx('--show-hero-fly-to-ty', 0);
      const cs = fS  + (tScale - fS)  * p;
      const cx = fTx + (tTx - fTx) * p;
      const cy = fTy + (tTy - fTy) * p;
      brandFly.style.transform = `translate(${cx}px, ${cy}px) scale(${cs})`;
      brandFly.style.opacity = (1 - d).toFixed(3);
      brandLogo.style.opacity = d.toFixed(3);

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
    // Wait one frame so auto-fit writes --show-hero-fly-* first.
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
    // toward target each tick. Both in -1..+1 range. `sampleTarget` is
    // a per-frame hook the coarse path uses to read `scrollY` inside
    // the rAF tick — reading scroll position from a scroll-event
    // handler forces a layout flush whenever the previous tick has
    // dirtied styles (the parallax writes 6 CSS vars on the shell),
    // and Lighthouse flagged it at ~14 ms. Inside the rAF the browser
    // has already laid out for the frame, so the read is free.
    let tx = 0, ty = 0, cx = 0, cy = 0;
    let running = false;
    let sampleTarget = null;

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
      if (sampleTarget) sampleTarget();
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
      // in its own magnitude direction. X stays at rest. Sample scrollY
      // inside the rAF tick (via sampleTarget) instead of in the scroll
      // event handler — see `sampleTarget` comment above. The scroll
      // listener only kicks the rAF; the tick reads scrollY when layout
      // is already current.
      sampleTarget = () => {
        ty = Math.min(1, scrollY / Math.max(innerHeight * 0.8, 1));
        tx = 0;
      };
      addEventListener('scroll', start, { passive: true });
      sampleTarget();
      start();
    }
  }

  // ---- 4. Hash-aware aria-current on the topbar "All Episodes" link ----
  // The link points at /episodes/#all-episodes and is rendered on every
  // page. It's only "current" when the user is actually focused on the
  // all-episodes section — i.e. the URL fragment matches. The server
  // can't see the hash, so flip the attribute client-side. show-hero.js
  // only loads on the episode-index, which keeps the behaviour scoped:
  // on subpages the link never carries aria-current at all, which is the
  // intended fallback.
  const allEpisodesLink = document.querySelector('[data-show-hero-all-episodes-link]');
  if (allEpisodesLink) {
    const sync = () => {
      if (location.hash === '#all-episodes') {
        allEpisodesLink.setAttribute('aria-current', 'page');
      } else {
        allEpisodesLink.removeAttribute('aria-current');
      }
    };
    sync();
    addEventListener('hashchange', sync);
  }
})();
