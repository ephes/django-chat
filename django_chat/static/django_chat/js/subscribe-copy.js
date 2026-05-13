(() => {
  const RESET_MS = 1800;

  document.addEventListener("click", async (event) => {
    const trigger = event.target.closest("[data-copy-target]");
    if (!trigger || !navigator.clipboard) return;

    event.preventDefault();
    const target = document.getElementById(trigger.dataset.copyTarget);
    if (!target) return;

    const text = (target.textContent || "").trim();
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      return;
    }

    trigger.dataset.copied = "true";
    const label = trigger.querySelector(".feed-action-label");
    if (label) label.textContent = label.dataset.copyDone || "Copied!";

    clearTimeout(trigger._copyResetId);
    trigger._copyResetId = setTimeout(() => {
      delete trigger.dataset.copied;
      if (label) label.textContent = label.dataset.copyDefault || "Copy URL";
    }, RESET_MS);
  });
})();
