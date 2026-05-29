(() => {
  const readyAttribute = "data-django-chat-player-ready";
  const loadingAttribute = "data-django-chat-player-loading";
  const loadStartedAttribute = "data-django-chat-player-load-started";
  const hoverLoadAttribute = "data-django-chat-load-on-hover";
  const hoverLoadArmedAttribute = "data-django-chat-hover-load-armed";
  const playerPanelStyleId = "django-chat-player-panel-style";
  const replayButtonA11yObserverAttribute = "data-django-chat-replay-a11y-observer";
  const playerPanelStyles = `
[data-test="tab"] {
  background: #e6f0dc !important;
  border: 1px solid #cdddc1 !important;
  border-radius: 16px !important;
  box-sizing: border-box;
  color: #14513a !important;
  margin: 12px !important;
}

[data-test="tab"]:not(#tab-transcripts) {
  max-height: 420px !important;
  overflow-x: hidden !important;
  overflow-y: auto !important;
}

#tab-transcripts {
  max-height: none !important;
}

[data-test="tab"] .tab-content {
  background-color: #e6f0dc !important;
  color: #14513a !important;
  line-height: 1.55;
}

[data-test="tab"] a,
[data-test="tab"] button,
[data-test="tab"] h1,
[data-test="tab"] h2,
[data-test="tab"] h3,
[data-test="tab"] h4,
[data-test="tab"] input,
[data-test="tab"] li,
[data-test="tab"] p,
[data-test="tab"] span {
  color: #14513a !important;
}

[data-test="tab-title"] {
  margin-bottom: 20px !important;
}

[data-test="tab-title--close"] {
  align-items: center !important;
  background: transparent !important;
  border: 0 !important;
  border-radius: 999px !important;
  cursor: pointer;
  display: inline-flex !important;
  height: 42px !important;
  justify-content: center !important;
  margin-top: -8px !important;
  padding: 0 !important;
  transition: background-color 0.15s ease, color 0.15s ease;
  width: 42px !important;
}

[data-test="tab"] [data-test="tab-title--close"] {
  color: #0d0d0d !important;
}

[data-test="tab-title--close"] svg {
  height: 22px !important;
  stroke-width: 3 !important;
  width: 22px !important;
}

[data-test="tab-title--close"] svg * {
  stroke: currentColor !important;
  stroke-width: 3 !important;
}

[data-test="tab-title--close"]:hover,
[data-test="tab-title--close"]:focus-visible {
  background: rgb(14 163 66 / 0.10) !important;
  color: #14513a !important;
  outline: none;
}

[data-test="tab-title--close"]:focus-visible {
  outline: 2px solid #0ea342 !important;
  outline-offset: 2px !important;
}

[data-test="tab-transcripts--follow"] {
  align-items: center !important;
  background: transparent !important;
  border: 1px solid #d8ded4 !important;
  border-radius: 999px !important;
  box-shadow: none !important;
  display: inline-flex !important;
  font-size: 0.92rem !important;
  font-weight: 600 !important;
  justify-content: center !important;
  min-height: 40px !important;
  padding: 0 16px !important;
  transition: background-color 0.15s ease, border-color 0.15s ease, color 0.15s ease;
  width: auto !important;
}

[data-test="tab"] [data-test="tab-transcripts--follow"] {
  color: #0d0d0d !important;
}

[data-test="tab-transcripts--follow"]:hover,
[data-test="tab-transcripts--follow"]:focus-visible {
  background: rgb(14 163 66 / 0.10) !important;
  border-color: #0ea342 !important;
  color: #14513a !important;
  outline: none;
}

[data-test="tab-transcripts--follow"]:focus-visible {
  outline: 2px solid #0ea342 !important;
  outline-offset: 2px !important;
}

[data-test="tab-transcripts--results"] {
  overflow-x: hidden !important;
  overflow-y: auto !important;
}

[data-test="divider"] {
  background: #d8d8d8 !important;
  background-image: none !important;
  background-size: auto !important;
}

[data-test="play-button"]:focus-visible {
  border-color: #0ea342 !important;
  border-radius: 999px !important;
  box-shadow: 0 0 0 2px #0ea342 !important;
  outline: none !important;
}

[data-test="play-button"]:focus:not(:focus-visible) {
  border-color: #0ea342 !important;
  border-radius: 999px !important;
  box-shadow: 0 0 0 2px #0ea342 !important;
  outline: none !important;
}

/* The compact Django Chat template has only icon-sized space for the simple
   Podlove play button. In the ended state Podlove still injects a textual
   "Replay" label into the restart button; without this override the label
   overflows the circular button and collides with the progress bar. The
   iframe observer below sets an explicit aria-label/title so the icon-only
   visual treatment still has an accessible name. */
button#play-button--restart [data-test="play-button--label"] {
  display: none !important;
}

button#play-button--restart > .wrapper > span {
  margin-left: 0 !important;
  margin-right: 0 !important;
  padding-left: 0 !important;
  padding-right: 0 !important;
}

[data-test^="tab-trigger--"] {
  border-radius: 8px !important;
  outline-color: #0ea342 !important;
}

[data-test^="tab-trigger--"]:focus-visible,
[data-test^="tab-trigger--"][aria-selected="true"] {
  border-color: #0ea342 !important;
  box-shadow: 0 0 0 2px #0ea342 !important;
  outline: none !important;
}

[data-test^="tab-trigger--"]:focus:not(:focus-visible) {
  border-color: #0ea342 !important;
  border-radius: 8px !important;
  outline: none !important;
}

[data-test^="tab-trigger--"][aria-selected="true"] * {
  border-color: #0ea342 !important;
}

/* Podlove renders the selected-tab marker as the final direct span child. */
[data-test^="tab-trigger--"][aria-selected="true"] > span:last-child,
[data-test^="tab-trigger--"][aria-selected="true"] > span:last-child svg,
[data-test^="tab-trigger--"][aria-selected="true"] > span:last-child path {
  color: #0ea342 !important;
  fill: #0ea342 !important;
  stroke: #0ea342 !important;
}

[data-test="tab-transcripts--results"] .active-transcript {
  background: linear-gradient(to top, rgb(14 163 66 / 0.28) 0 42%, transparent 42%) !important;
  border-radius: 2px;
  color: #0d0d0d !important;
}
`;

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

  const installPlayerPanelStyles = (iframeDocument) => {
    if (!iframeDocument || iframeDocument.getElementById(playerPanelStyleId)) {
      return;
    }

    const style = iframeDocument.createElement("style");
    style.id = playerPanelStyleId;
    style.setAttribute("data-django-chat-player-style", "");
    style.textContent = playerPanelStyles;
    (iframeDocument.head || iframeDocument.documentElement).appendChild(style);
  };

  const syncReplayButtonA11y = (iframeDocument) => {
    const iframeWindow = iframeDocument?.defaultView;
    const restartButton = iframeDocument?.querySelector("button#play-button--restart");
    if (!iframeWindow || !(restartButton instanceof iframeWindow.HTMLButtonElement)) {
      return;
    }

    restartButton.setAttribute("aria-label", "Replay");
    restartButton.setAttribute("title", "Replay");
  };

  const installReplayButtonA11y = (iframeDocument) => {
    const root = iframeDocument?.getElementById("app");
    if (!root || root.hasAttribute(replayButtonA11yObserverAttribute)) {
      return;
    }

    root.setAttribute(replayButtonA11yObserverAttribute, "true");
    syncReplayButtonA11y(iframeDocument);

    const Observer = iframeDocument.defaultView?.MutationObserver || MutationObserver;
    const observer = new Observer(() => syncReplayButtonA11y(iframeDocument));
    // Only the explicit aria-label is authoritative for accessibility. The title is
    // best-effort tooltip text; do not observe title/aria-label here, because our own
    // setAttribute calls would otherwise create an attribute-mutation feedback loop.
    observer.observe(root, {
      attributeFilter: ["id"],
      attributes: true,
      childList: true,
      subtree: true,
    });
  };

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
        installPlayerPanelStyles(iframeDocument);
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
        installReplayButtonA11y(iframeDocument);
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
