(() => {
  const header = document.querySelector(".site-header");
  if (!header) return;

  const HIDE_AFTER = 120;
  const DELTA = 4;

  // Sentinel marks the threshold below which the header always stays
  // visible. IntersectionObserver flips a flag when the sentinel leaves
  // or re-enters the viewport, so the scroll handler never has to read
  // `scrollY` to answer "are we past the threshold yet?" — that read
  // would otherwise force a layout flush on every scroll tick.
  const sentinel = document.createElement("div");
  sentinel.setAttribute("aria-hidden", "true");
  sentinel.style.cssText =
    "position:absolute;top:" + HIDE_AFTER +
    "px;left:0;width:1px;height:1px;pointer-events:none;";
  document.body.prepend(sentinel);

  let pastThreshold = false;
  let lastY = window.scrollY;
  let ticking = false;
  let hidden = false;

  const setHidden = (val) => {
    if (val === hidden) return;
    hidden = val;
    header.classList.toggle("site-header--hidden", val);
  };

  new IntersectionObserver(
    ([entry]) => {
      pastThreshold = !entry.isIntersecting;
      if (pastThreshold) {
        // The scroll handler skips its `scrollY` read while we're below
        // the threshold, which would leave `lastY` stale across a
        // round-trip (down past 120 → back above → down again). Refresh
        // the baseline whenever we re-enter hide-eligible territory so
        // the next direction comparison is measured from a real
        // position. The IO callback fires post-layout, so this read
        // doesn't cost a reflow.
        lastY = window.scrollY;
      } else {
        setHidden(false);
      }
    },
    { threshold: 0 },
  ).observe(sentinel);

  const update = () => {
    ticking = false;
    if (!pastThreshold) return;
    const y = window.scrollY;
    const delta = y - lastY;
    lastY = y;
    if (delta > DELTA) setHidden(true);
    else if (delta < -DELTA) setHidden(false);
  };

  window.addEventListener(
    "scroll",
    () => {
      if (!ticking) {
        requestAnimationFrame(update);
        ticking = true;
      }
    },
    { passive: true },
  );
})();
