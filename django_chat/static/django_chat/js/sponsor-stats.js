(() => {
  const stats = document.querySelectorAll(".sponsor-stat");
  if (!stats.length) return;
  if (!("IntersectionObserver" in window)) return;
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;

  const parseValue = (raw) => {
    const match = raw.match(/^([^\d-]*)(-?[\d,.]+)(.*)$/);
    if (!match) return null;
    const [, prefix, numStr, suffix] = match;
    const cleaned = numStr.replace(/,/g, "");
    const numeric = parseFloat(cleaned);
    if (!Number.isFinite(numeric)) return null;
    const decimals = (cleaned.split(".")[1] || "").length;
    const hasComma = numStr.includes(",");
    return { prefix, numeric, decimals, hasComma, suffix };
  };

  const format = (n, info) => {
    let body;
    if (info.decimals > 0) {
      body = n.toFixed(info.decimals);
    } else {
      body = Math.round(n).toString();
      if (info.hasComma) body = body.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
    }
    return `${info.prefix}${body}${info.suffix}`;
  };

  const countUp = (el, info, duration = 1400) => {
    const start = performance.now();
    const ease = (t) => 1 - Math.pow(1 - t, 3);
    const tick = (now) => {
      const t = Math.min(1, (now - start) / duration);
      el.textContent = format(info.numeric * ease(t), info);
      if (t < 1) requestAnimationFrame(tick);
      else el.textContent = format(info.numeric, info);
    };
    requestAnimationFrame(tick);
  };

  const reveal = (stat) => {
    stat.classList.add("is-revealed");
    const valueEl = stat.querySelector(".sponsor-stat-value");
    if (!valueEl) return;
    const raw = valueEl.dataset.statValue || valueEl.textContent || "";
    const info = parseValue(raw);
    if (!info) return;
    valueEl.textContent = format(0, info);
    setTimeout(() => countUp(valueEl, info), 220);
  };

  const io = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (!entry.isIntersecting) continue;
        reveal(entry.target);
        io.unobserve(entry.target);
      }
    },
    { threshold: 0.4 },
  );

  for (const stat of stats) io.observe(stat);
})();
