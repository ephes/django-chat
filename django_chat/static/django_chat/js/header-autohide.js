(() => {
  const header = document.querySelector(".site-header");
  if (!header) return;

  const HIDE_AFTER = 120;
  const DELTA = 4;

  let lastY = window.scrollY;
  let ticking = false;

  const update = () => {
    const y = window.scrollY;
    const delta = y - lastY;

    if (y < HIDE_AFTER) {
      header.classList.remove("site-header--hidden");
    } else if (delta > DELTA) {
      header.classList.add("site-header--hidden");
    } else if (delta < -DELTA) {
      header.classList.remove("site-header--hidden");
    }

    lastY = y;
    ticking = false;
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
