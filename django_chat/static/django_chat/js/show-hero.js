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

  // Measure the flight endpoints used by CSS scroll animations and the JS
  // polyfill so the logo aligns with the hero mark and the docked topbar mark.
  if (heroLogo && brandLogo && brandFly && heroLogoImg) {
    const fit = () => {
      // Measure the unanimated fly-twin even if this refit happens mid-flight.
      const prevAnim = brandFly.style.animationName;
      const prevTransform = brandFly.style.transform;
      brandFly.style.animationName = 'none';
      brandFly.style.transform = 'none';
      const f = brandFly.getBoundingClientRect();
      const b = brandLogo.getBoundingClientRect();
      const h = heroLogoImg.getBoundingClientRect();
      const sy = window.scrollY;
      brandFly.style.transform = prevTransform;
      brandFly.style.animationName = prevAnim;

      if (!f.height || !h.height || !b.height) return false;

      // The hero mark is in flow; normalize it to a scroll-0 document position.
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
      return true;
    };

    // The [data-show-hero-morph] marker gates the @supports scroll-morph AND
    // lays out .brand-mark-fly (display:block) so fit() can measure it. Set it
    // for the attempt, then roll it back if measuring failed (and it wasn't
    // already established) — so a no-JS / pre-measure render keeps the static
    // hero fallback instead of flashing an oversized, unmeasured fly. Marker
    // and fit run in one task, so a successful first reveal never paints the
    // intermediate state.
    const reveal = () => {
      if (!shell) { fit(); return; }
      const established = shell.hasAttribute('data-show-hero-morph');
      if (!established) shell.setAttribute('data-show-hero-morph', '');
      if (!fit() && !established) shell.removeAttribute('data-show-hero-morph');
    };

    reveal();
    addEventListener('load', reveal);
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(reveal);

    // rAF-throttle ResizeObserver bursts to one reveal per frame.
    let pending = false;
    const schedule = () => {
      if (pending) return;
      pending = true;
      requestAnimationFrame(() => { pending = false; reveal(); });
    };
    const ro = new ResizeObserver(schedule);
    if (shell) ro.observe(shell);
    ro.observe(heroLogoImg);
  }

  // Fallback for browsers without native scroll-driven animations.
  if (!hasNativeTimeline && !reduced && brand && brandLogo && brandFly && brandName && heroLogo) {
    brand.style.visibility = 'visible';
    brand.style.pointerEvents = 'auto';
    heroLogo.style.visibility = 'hidden';
    brandName.style.animationName = 'none';
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
    brandLogo.style.opacity = '0';

    const readPx = (name, fallbackPx) => {
      const v = getComputedStyle(root).getPropertyValue(name).trim();
      const n = parseFloat(v);
      return Number.isFinite(n) ? n : fallbackPx;
    };
    // Cubic ease-out, matching cubic-bezier(.2, .7, .2, 1) closely enough here.
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
      const p = ease(ramp(s, mS, mE));
      const d = ramp(s, dS, mE);
      const q = ease(ramp(s, tS, tE));

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
    // Wait one frame so auto-fit writes the flight variables first.
    requestAnimationFrame(update);
  }

  // Subtle hero parallax. Writes scoped CSS vars on the shell only.
  if (!reduced && shell) {
    const M = {
      hp:      { x: -0.4, y: -0.25 },
      outline: { x: -0.4, y: -0.25 },
      fill:    { x:  0.4, y:  0.25 },
    };

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
      // Coarse pointer / touch: scroll-linked Y drift.
      sampleTarget = () => {
        ty = Math.min(1, scrollY / Math.max(innerHeight * 0.8, 1));
        tx = 0;
      };
      addEventListener('scroll', start, { passive: true });
      sampleTarget();
      start();
    }
  }

  // The server cannot see URL fragments, so mark the topbar link client-side.
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
