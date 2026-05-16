(() => {
  const dialog = document.getElementById("embed-dialog");
  if (!dialog || typeof dialog.showModal !== "function") return;

  const embedUrl = dialog.dataset.embedUrl;
  const embedTitle = dialog.dataset.embedTitle || "Episode";
  if (!embedUrl) return;

  const trigger = document.querySelector('[data-action="embed"]');
  const closeButton = dialog.querySelector("[data-embed-close]");
  const snippetInput = dialog.querySelector("[data-embed-snippet]");
  const copyButton = dialog.querySelector("[data-embed-copy]");
  const copyLabel = dialog.querySelector("[data-embed-copy-label]");

  const escapeAttr = (value) =>
    String(value).replace(/&/g, "&amp;").replace(/"/g, "&quot;");

  const buildSnippet = () =>
    `<iframe src="${escapeAttr(embedUrl)}" title="${escapeAttr(embedTitle)}" width="100%" height="200" scrolling="no" loading="lazy" allow="autoplay" style="border:0"></iframe>`;

  const render = () => {
    if (snippetInput) {
      snippetInput.value = buildSnippet();
    }
  };

  const clearFragment = () => {
    if (location.hash === `#${dialog.id}`) {
      history.replaceState(null, "", location.pathname + location.search);
    }
  };

  const openDialog = () => {
    render();
    clearFragment();
    if (!dialog.open) dialog.showModal();
  };

  trigger?.addEventListener("click", (event) => {
    event.preventDefault();
    openDialog();
  });

  if (location.hash === `#${dialog.id}`) {
    openDialog();
  }

  closeButton?.addEventListener("click", (event) => {
    event.preventDefault();
    if (dialog.open) dialog.close();
    clearFragment();
  });

  dialog.addEventListener("click", (event) => {
    if (event.target === dialog) dialog.close();
  });

  const copyToClipboard = async (text) => {
    if (navigator.clipboard?.writeText) {
      try {
        await navigator.clipboard.writeText(text);
        return true;
      } catch {
        // fall through
      }
    }
    if (snippetInput) {
      snippetInput.removeAttribute("readonly");
      snippetInput.select();
      try {
        const ok = document.execCommand("copy");
        snippetInput.setAttribute("readonly", "readonly");
        return ok;
      } catch {
        snippetInput.setAttribute("readonly", "readonly");
        return false;
      }
    }
    return false;
  };

  copyButton?.addEventListener("click", async () => {
    const ok = await copyToClipboard(buildSnippet());
    if (copyLabel) {
      copyLabel.textContent = ok ? "Copied!" : "Press ⌘C";
      window.setTimeout(() => {
        copyLabel.textContent = "Copy";
      }, 2000);
    }
  });

  render();
})();
