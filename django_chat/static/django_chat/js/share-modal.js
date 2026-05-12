(() => {
  const dialog = document.getElementById("share-dialog");
  if (!dialog || typeof dialog.showModal !== "function") return;

  const baseUrl = dialog.dataset.shareUrl || window.location.href;
  const title = dialog.dataset.shareTitle || document.title;

  const trigger = document.querySelector('[data-action="share"]');
  const closeButton = dialog.querySelector("[data-share-close]");
  const startToggle = dialog.querySelector("[data-startat-toggle]");
  const startInput = dialog.querySelector("[data-startat-time]");
  const urlInput = dialog.querySelector("[data-share-url-input]");
  const copyButton = dialog.querySelector("[data-share-copy]");
  const copyLabel = dialog.querySelector("[data-share-copy-label]");
  const pills = dialog.querySelectorAll(".share-pill");
  const mastodonPrompt = dialog.querySelector("[data-mastodon-prompt]");
  const mastodonInstance = dialog.querySelector("[data-mastodon-instance]");
  const mastodonSubmit = dialog.querySelector("[data-mastodon-submit]");
  const mastodonForget = dialog.querySelector("[data-mastodon-forget]");
  const mastodonStatus = dialog.querySelector("[data-mastodon-status]");
  const mastodonStatusHost = dialog.querySelector("[data-mastodon-status-host]");

  const MASTODON_KEY = "django-chat:mastodon-instance";

  // localStorage may throw (private mode, disabled cookies, sandboxed iframes).
  // The share modal must still work without persistent Mastodon caching.
  const safeStorage = {
    get(key) {
      try { return localStorage.getItem(key); } catch { return null; }
    },
    set(key, value) {
      try { localStorage.setItem(key, value); } catch {}
    },
    remove(key) {
      try { localStorage.removeItem(key); } catch {}
    },
  };

  const parseTimecode = (raw) => {
    if (!raw) return null;
    const trimmed = raw.trim();
    const match = /^(\d{1,3}):([0-5]\d)$/.exec(trimmed);
    if (!match) return null;
    return Number(match[1]) * 60 + Number(match[2]);
  };

  const buildShareUrl = () => {
    if (!startToggle?.checked) return baseUrl;
    const seconds = parseTimecode(startInput?.value);
    if (seconds == null) return baseUrl;
    const url = new URL(baseUrl);
    url.searchParams.set("t", String(seconds));
    return url.toString();
  };

  const renderPills = () => {
    const sharedUrl = buildShareUrl();
    if (urlInput) urlInput.value = sharedUrl;

    pills.forEach((pill) => {
      const net = pill.dataset.shareNet;
      if (!net) return;
      const encodedUrl = encodeURIComponent(sharedUrl);
      const encodedTitle = encodeURIComponent(title);
      let href = null;
      switch (net) {
        case "twitter":
          href = `https://twitter.com/intent/tweet?url=${encodedUrl}&text=${encodedTitle}`;
          break;
        case "facebook":
          href = `https://www.facebook.com/sharer/sharer.php?u=${encodedUrl}`;
          break;
        case "linkedin":
          href = `https://www.linkedin.com/sharing/share-offsite/?url=${encodedUrl}`;
          break;
        case "email":
          href = `mailto:?subject=${encodedTitle}&body=${encodedUrl}`;
          break;
        case "mastodon":
          return;
      }
      if (href && pill.tagName === "A") pill.href = href;
    });
  };

  const openMastodonPrompt = () => {
    if (!mastodonPrompt) return;
    mastodonPrompt.hidden = false;
    mastodonInstance?.focus();
  };

  const closeMastodonPrompt = () => {
    if (mastodonPrompt) mastodonPrompt.hidden = true;
  };

  const sanitizeInstance = (value) => {
    if (!value) return null;
    let host = value.trim().replace(/^https?:\/\//, "").replace(/\/.*$/, "");
    host = host.replace(/^@/, "");
    if (!/^[a-z0-9.-]+\.[a-z]{2,}$/i.test(host)) return null;
    return host;
  };

  const openMastodonShare = (instance) => {
    const sharedUrl = buildShareUrl();
    const text = `${title} ${sharedUrl}`.trim();
    const target = `https://${instance}/share?text=${encodeURIComponent(text)}`;
    window.open(target, "_blank", "noopener,noreferrer");
  };

  const updateMastodonStatus = () => {
    const stored = safeStorage.get(MASTODON_KEY);
    if (mastodonStatus) {
      mastodonStatus.hidden = !stored;
      if (stored && mastodonStatusHost) {
        mastodonStatusHost.textContent = stored;
      }
    }
  };

  trigger?.addEventListener("click", (event) => {
    event.preventDefault();
    renderPills();
    closeMastodonPrompt();
    updateMastodonStatus();
    dialog.showModal();
  });

  closeButton?.addEventListener("click", () => dialog.close());

  // Close on backdrop click (click directly on dialog, not its inner content).
  dialog.addEventListener("click", (event) => {
    if (event.target === dialog) dialog.close();
  });

  startToggle?.addEventListener("change", () => {
    if (startInput) startInput.disabled = !startToggle.checked;
    if (startToggle.checked) startInput?.focus();
    renderPills();
  });

  startInput?.addEventListener("input", () => {
    renderPills();
  });

  const copyToClipboard = async (text) => {
    if (navigator.clipboard?.writeText) {
      try {
        await navigator.clipboard.writeText(text);
        return true;
      } catch (err) {
        // fall through to legacy fallback
      }
    }
    if (urlInput) {
      urlInput.removeAttribute("readonly");
      urlInput.select();
      try {
        const ok = document.execCommand("copy");
        urlInput.setAttribute("readonly", "readonly");
        return ok;
      } catch (err) {
        urlInput.setAttribute("readonly", "readonly");
        return false;
      }
    }
    return false;
  };

  copyButton?.addEventListener("click", async () => {
    const ok = await copyToClipboard(buildShareUrl());
    if (copyLabel) {
      copyLabel.textContent = ok ? "Copied!" : "Press ⌘C";
      window.setTimeout(() => {
        copyLabel.textContent = "Copy";
      }, 2000);
    }
  });

  // Mastodon click → either use stored instance or show inline prompt.
  pills.forEach((pill) => {
    if (pill.dataset.shareNet !== "mastodon") return;
    pill.addEventListener("click", (event) => {
      event.preventDefault();
      const stored = safeStorage.get(MASTODON_KEY);
      if (stored) {
        openMastodonShare(stored);
        return;
      }
      openMastodonPrompt();
    });
  });

  const submitMastodon = () => {
    const host = sanitizeInstance(mastodonInstance?.value || "");
    if (!host) {
      mastodonInstance?.focus();
      mastodonInstance?.setAttribute("aria-invalid", "true");
      return;
    }
    mastodonInstance?.removeAttribute("aria-invalid");
    safeStorage.set(MASTODON_KEY, host);
    closeMastodonPrompt();
    updateMastodonStatus();
    openMastodonShare(host);
  };

  mastodonSubmit?.addEventListener("click", submitMastodon);
  mastodonInstance?.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      submitMastodon();
    }
  });

  mastodonForget?.addEventListener("click", (event) => {
    event.preventDefault();
    safeStorage.remove(MASTODON_KEY);
    if (mastodonInstance) {
      mastodonInstance.value = "";
      mastodonInstance.removeAttribute("aria-invalid");
    }
    updateMastodonStatus();
    openMastodonPrompt();
  });

  // Initialize pill hrefs so right-click → "Copy link" works without opening dialog.
  renderPills();
  updateMastodonStatus();
})();
