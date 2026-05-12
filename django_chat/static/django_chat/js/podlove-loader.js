(() => {
  const readyAttribute = "data-django-chat-player-ready";
  const loadingAttribute = "data-django-chat-player-loading";
  const loadStartedAttribute = "data-django-chat-player-load-started";
  const hoverLoadAttribute = "data-django-chat-load-on-hover";
  const hoverLoadArmedAttribute = "data-django-chat-hover-load-armed";

  // Parse ?t=<seconds | MM:SS | HH:MM:SS> from the page URL. Returns whole seconds or null.
  // Each segment must be digits only; minutes and seconds are clamped to 0..59 in colon forms.
  const parseStartAt = (search) => {
    const raw = new URLSearchParams(search).get("t");
    if (!raw) return null;
    if (/^\d+$/.test(raw)) {
      const n = Number(raw);
      return Number.isFinite(n) && n >= 0 ? Math.floor(n) : null;
    }
    if (!/^\d+:\d+(?::\d+)?$/.test(raw)) return null;
    const parts = raw.split(":").map((p) => Number(p));
    if (parts.length === 2) {
      const [m, s] = parts;
      if (s > 59) return null;
      return m * 60 + s;
    }
    const [h, m, s] = parts;
    if (m > 59 || s > 59) return null;
    return h * 3600 + m * 60 + s;
  };
  const startAtSeconds = parseStartAt(window.location.search);

  const markReady = (player) => {
    player.removeAttribute(loadingAttribute);
    player.setAttribute(readyAttribute, "true");
    player
      .querySelectorAll("[data-django-chat-player-placeholder]")
      .forEach((placeholder) => {
        placeholder.removeAttribute("aria-busy");
        placeholder.setAttribute("aria-hidden", "true");
        placeholder.setAttribute("tabindex", "-1");
        if (placeholder === document.activeElement) {
          placeholder.blur();
        }
      });
  };

  const markLoading = (player) => {
    player.removeAttribute(readyAttribute);
    player.setAttribute(loadingAttribute, "true");
    player
      .querySelectorAll("[data-django-chat-player-placeholder]")
      .forEach((placeholder) => {
        placeholder.setAttribute("aria-busy", "true");
        placeholder.setAttribute("aria-label", "Loading audio player");
      });
  };

  const loadPlayer = (player) => {
    if (player.hasAttribute(loadStartedAttribute) || player.querySelector("iframe")) {
      return;
    }

    player.setAttribute(loadStartedAttribute, "true");
    markLoading(player);

    const schedule = () => {
      if (typeof player.scheduleInitialize === "function") {
        player.scheduleInitialize();
        return;
      }

      const fallbackButton = player.querySelector(".podlove-player-button");
      if (fallbackButton instanceof HTMLButtonElement) {
        // Fallback: trigger Podlove's native click-to-load handler on the facade button.
        fallbackButton.click();
      }
    };

    if (window.customElements?.whenDefined) {
      window.customElements.whenDefined("podlove-player").then(schedule).catch(schedule);
    } else {
      schedule();
    }
  };

  const armHoverLoad = (player) => {
    if (
      player.getAttribute(hoverLoadAttribute) !== "true" ||
      player.hasAttribute(hoverLoadArmedAttribute)
    ) {
      return;
    }

    player.setAttribute(hoverLoadArmedAttribute, "true");
    const trigger = () => loadPlayer(player);
    const triggerMouseHover = (event) => {
      if (event.pointerType && event.pointerType !== "mouse") {
        return;
      }
      trigger();
    };
    player.addEventListener("pointerenter", triggerMouseHover, { passive: true });
    player.addEventListener("focusin", trigger);
    player
      .querySelectorAll("[data-django-chat-player-placeholder]")
      .forEach((placeholder) => placeholder.addEventListener("click", trigger, { once: true }));
  };

  const watchIframe = (player, iframe) => {
    let appObserver = null;
    let appLookupObserver = null;
    let isReady = false;
    let revealFallback = null;
    let revealWhenLoaded = null;

    const cleanup = () => {
      iframe.removeEventListener("load", revealWhenLoaded);
      appObserver?.disconnect();
      appLookupObserver?.disconnect();
      window.clearTimeout(revealFallback);
    };

    const reveal = () => {
      if (isReady) {
        return;
      }
      isReady = true;
      cleanup();
      markReady(player);
    };

    revealFallback = window.setTimeout(reveal, 3000);

    revealWhenLoaded = () => {
      try {
        const iframeDocument = iframe.contentDocument;
        const app = iframeDocument?.getElementById("app");
        if (!app) {
          if (iframeDocument && !appLookupObserver) {
            appLookupObserver = new MutationObserver(() => {
              revealWhenLoaded();
            });
            appLookupObserver.observe(iframeDocument, { childList: true, subtree: true });
          }
          return false;
        }
        if (app.classList.contains("loaded")) {
          reveal();
          return true;
        }

        appLookupObserver?.disconnect();
        appLookupObserver = null;
        if (appObserver) {
          return true;
        }
        appObserver = new MutationObserver(() => {
          if (app.classList.contains("loaded")) {
            reveal();
          }
        });
        appObserver.observe(app, { attributes: true, attributeFilter: ["class"] });
        return true;
      } catch {
        reveal();
        return true;
      }
    };

    iframe.addEventListener("load", revealWhenLoaded, { once: true });
    revealWhenLoaded();
  };

  const watchPlayer = (player) => {
    const iframe = player.querySelector("iframe");
    if (iframe) {
      watchIframe(player, iframe);
      return;
    }

    const waitsForUserLoad = player.getAttribute("data-load-mode") === "click";
    let revealFallback = null;
    const observer = new MutationObserver(() => {
      const iframe = player.querySelector("iframe");
      if (iframe) {
        window.clearTimeout(revealFallback ?? undefined);
        observer.disconnect();
        watchIframe(player, iframe);
      }
    });
    observer.observe(player, { childList: true, subtree: true });

    // Click-to-load players should only become ready after Podlove inserts an iframe.
    if (!waitsForUserLoad) {
      revealFallback = window.setTimeout(() => {
        observer.disconnect();
        markReady(player);
      }, 4000);
    }
  };

  // NOTE: Receiver-side auto-seek is intentionally not implemented yet.
  //
  // Two earlier attempts were tried and both proved unreliable:
  //   1. `iframe.contentWindow.postMessage({ type: "REQUEST_PLAYTIME", payload })` — that
  //      shape is Podlove's internal Redux action and is not exposed to external messages
  //      through the iframe-resizer plumbing.
  //   2. Setting the parent's `window.location.hash` to `#t=HH:MM:SS` — Podlove's iframe
  //      is initialized without iframe-resizer's `inPageLinks` option, so parent hash
  //      changes do not propagate, and the player's own `?t=` share parser reads the
  //      iframe's own `window.location.search`, not the parent's.
  //
  // The URL convention is already shipped on the producer side via the Share modal. When
  // staging gains a real audio episode we can verify which integration path Podlove
  // actually supports (iframe-src injection, config-prefetch with `playtime`, custom
  // events) and wire it here. Until then `parseStartAt` is exposed so the auto-load gate
  // below stays meaningful.

  const init = () => {
    document.querySelectorAll("podlove-player").forEach((player) => {
      armHoverLoad(player);
      watchPlayer(player);
      if (startAtSeconds != null) {
        // A shared URL with ?t= signals intent to play from that point. Bypass the click-
        // to-load gate so the player is ready immediately; receiver-side seek wiring is
        // tracked in the file comment above.
        loadPlayer(player);
      }
    });
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, { once: true });
  } else {
    init();
  }
})();
