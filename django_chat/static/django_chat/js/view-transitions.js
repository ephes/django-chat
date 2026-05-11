(() => {
  const supportsNavigationApi = "navigation" in window;
  const supportsTransitionEvents = "onpageswap" in window && "onpagereveal" in window;
  const supportsViewTransitionStyles =
    window.CSS &&
    typeof window.CSS.supports === "function" &&
    window.CSS.supports("view-transition-name: none");

  if (!supportsNavigationApi || !supportsTransitionEvents || !supportsViewTransitionStyles) {
    return;
  }

  const reduceMotion =
    typeof window.matchMedia === "function"
      ? window.matchMedia("(prefers-reduced-motion: reduce)")
      : null;
  let pendingEpisodeSlug = "";
  let pendingFilterNavigation = false;
  let indexNavigationController = null;
  let indexTransitionId = 0;
  let lastIndexUrl = null;
  let suppressPaginationPopstateUrl = "";
  let lastPaginationUrl = `${window.location.pathname}${window.location.search}`;
  const storageKeys = {
    episodeIndexUrl: "djangoChatEpisodeIndexUrl",
  };

  const transitionNames = {
    episodeBadge: "dc-episode-badge",
    episodeTitle: "dc-episode-title",
    results: "dc-episode-results",
  };

  const addType = (viewTransition, type) => {
    if (viewTransition && viewTransition.types && viewTransition.types.add) {
      viewTransition.types.add(type);
    }
  };

  const cleanAfterSnapshots = (viewTransition, entries) => {
    if (!entries.length) {
      return;
    }

    let cleaned = false;
    const cleanup = () => {
      if (cleaned) {
        return;
      }
      cleaned = true;
      entries.forEach(({ element, previousName }) => {
        if (previousName) {
          element.style.setProperty("view-transition-name", previousName);
        } else {
          element.style.removeProperty("view-transition-name");
        }
      });
    };

    if (viewTransition && viewTransition.ready) {
      viewTransition.ready.finally(cleanup);
    }
    if (viewTransition && viewTransition.finished) {
      viewTransition.finished.finally(cleanup);
    }
  };

  const nameElement = (element, name) => {
    if (!(element instanceof HTMLElement)) {
      return [];
    }

    const previousName = element.style.getPropertyValue("view-transition-name");
    element.style.setProperty("view-transition-name", name);
    return [{ element, previousName }];
  };

  const isPlainNavigationClick = (event, link) =>
    event instanceof MouseEvent &&
    event.button === 0 &&
    !event.altKey &&
    !event.ctrlKey &&
    !event.metaKey &&
    !event.shiftKey &&
    !link.hasAttribute("download") &&
    (!link.target || link.target === "_self");

  const restoreNamedElements = (entries) => {
    entries.forEach(({ element, previousName }) => {
      if (previousName) {
        element.style.setProperty("view-transition-name", previousName);
      } else {
        element.style.removeProperty("view-transition-name");
      }
    });
  };

  const getActivationUrl = (activation) => {
    const url = activation && activation.entry && activation.entry.url;
    return typeof url === "string" ? new URL(url) : null;
  };

  const getPreviousUrl = (activation) => {
    const url = activation && activation.from && activation.from.url;
    return typeof url === "string" ? new URL(url) : null;
  };

  const pageNumber = (url) => {
    const value = Number.parseInt(url.searchParams.get("page") || "1", 10);
    return Number.isFinite(value) && value > 0 ? value : 1;
  };

  const searchWithoutPage = (url) => {
    const params = new URLSearchParams(url.search);
    params.delete("page");
    return Array.from(params.entries())
      .sort(([leftKey, leftValue], [rightKey, rightValue]) => {
        const left = `${leftKey}=${leftValue}`;
        const right = `${rightKey}=${rightValue}`;
        return left.localeCompare(right);
      })
      .map(([key, value]) => `${key}=${value}`)
      .join("&");
  };

  const slugFromUrl = (url) => {
    const parts = url.pathname.split("/").filter(Boolean);
    return parts[parts.length - 1] || "";
  };

  const activePage = () => {
    const page = document.querySelector("[data-vt-page]");
    return page ? page.getAttribute("data-vt-page") || "" : "";
  };

  const activeEpisodeSlug = () => {
    const episode = document.querySelector("[data-vt-page='episode-detail'][data-vt-episode-slug]");
    return episode ? episode.getAttribute("data-vt-episode-slug") || "" : "";
  };

  const rememberEpisodeIndexUrl = (episodeSlug) => {
    if (activePage() !== "episode-index") {
      return;
    }

    try {
      window.sessionStorage.setItem(
        storageKeys.episodeIndexUrl,
        JSON.stringify({ episodeSlug, url: window.location.href }),
      );
    } catch {
      // Storage can be disabled; the static fallback link still works.
    }
  };

  const rememberedEpisodeIndexUrl = () => {
    try {
      const value = window.sessionStorage.getItem(storageKeys.episodeIndexUrl);
      if (!value) {
        return null;
      }
      const stored = JSON.parse(value);
      if (!stored || stored.episodeSlug !== activeEpisodeSlug()) {
        return null;
      }
      return new URL(stored.url);
    } catch {
      return null;
    }
  };

  const restoreBackLink = () => {
    if (activePage() !== "episode-detail") {
      return;
    }

    const backLink = document.querySelector(".back-link[href]");
    const indexUrl = rememberedEpisodeIndexUrl();
    if (!(backLink instanceof HTMLAnchorElement) || !indexUrl) {
      return;
    }

    const fallbackUrl = new URL(backLink.href, window.location.href);
    if (indexUrl.origin !== window.location.origin || indexUrl.pathname !== fallbackUrl.pathname) {
      return;
    }

    backLink.href = `${indexUrl.pathname}${indexUrl.search}${indexUrl.hash}`;
  };

  const initPage = () => {
    restoreBackLink();
    if (activePage() === "episode-index") {
      lastIndexUrl = new URL(window.location.href);
    }
  };

  const findEpisodeTitle = (slug) => {
    if (activePage() === "episode-detail") {
      return document.querySelector("[data-vt-page='episode-detail'] [data-vt-episode-title]");
    }

    if (!slug) {
      return null;
    }

    const escapedSlug = window.CSS && window.CSS.escape ? window.CSS.escape(slug) : slug;
    return document.querySelector(`[data-vt-episode-slug="${escapedSlug}"] [data-vt-episode-title]`);
  };

  const findEpisodeBadge = (slug) => {
    if (activePage() === "episode-detail") {
      return document.querySelector("[data-vt-page='episode-detail'] [data-vt-episode-badge]");
    }

    if (!slug) {
      return null;
    }

    const escapedSlug = window.CSS && window.CSS.escape ? window.CSS.escape(slug) : slug;
    return document.querySelector(`[data-vt-episode-slug="${escapedSlug}"] [data-vt-episode-badge]`);
  };

  const classifyIndexNavigation = (fromUrl, toUrl) => {
    if (fromUrl.pathname !== toUrl.pathname) {
      return null;
    }

    if (pendingFilterNavigation || searchWithoutPage(fromUrl) !== searchWithoutPage(toUrl)) {
      return { kind: "filter" };
    }

    return null;
  };

  const classifyBeforeNavigation = (fromUrl, toUrl) => {
    if (fromUrl.origin !== toUrl.origin || (reduceMotion && reduceMotion.matches)) {
      return null;
    }

    const page = activePage();
    if (page === "episode-index") {
      const indexNavigation = classifyIndexNavigation(fromUrl, toUrl);
      if (indexNavigation) {
        return indexNavigation;
      }

      if (fromUrl.pathname !== toUrl.pathname) {
        return { episodeSlug: slugFromUrl(toUrl) || pendingEpisodeSlug, kind: "episode" };
      }
    }

    if (page === "episode-detail" && fromUrl.pathname !== toUrl.pathname) {
      return { episodeSlug: activeEpisodeSlug() || slugFromUrl(fromUrl), kind: "episode" };
    }

    return null;
  };

  const classifyAfterNavigation = (fromUrl, toUrl) => {
    if (fromUrl.origin !== toUrl.origin || (reduceMotion && reduceMotion.matches)) {
      return null;
    }

    const page = activePage();
    if (page === "episode-index") {
      const indexNavigation = classifyIndexNavigation(fromUrl, toUrl);
      if (indexNavigation) {
        return indexNavigation;
      }

      if (fromUrl.pathname !== toUrl.pathname) {
        return { episodeSlug: slugFromUrl(fromUrl), kind: "episode" };
      }
    }

    if (page === "episode-detail" && fromUrl.pathname !== toUrl.pathname) {
      return { episodeSlug: activeEpisodeSlug() || slugFromUrl(toUrl), kind: "episode" };
    }

    return null;
  };

  const htmlFromUrl = async (url, signal) => {
    // Prototype path: fetch the full server-rendered page and extract the results container.
    const response = await fetch(url, {
      credentials: "same-origin",
      headers: { "X-Requested-With": "XMLHttpRequest" },
      signal,
    });
    if (!response.ok) {
      throw new Error(`Pagination request failed: ${response.status}`);
    }
    return new DOMParser().parseFromString(await response.text(), "text/html");
  };

  const replaceFilterForm = (nextDocument) => {
    const currentForm = document.querySelector(".filter-form");
    const nextForm = nextDocument.querySelector(".filter-form");
    if (!currentForm || !nextForm) {
      return false;
    }
    currentForm.replaceWith(nextForm.cloneNode(true));
    return true;
  };

  const replaceEpisodeResults = (currentResults, nextResults, previousName) => {
    nextResults.setAttribute("aria-busy", currentResults.getAttribute("aria-busy") || "false");
    nextResults.style.setProperty("view-transition-name", transitionNames.results);
    currentResults.replaceWith(nextResults);

    return [{ element: nextResults, previousName }];
  };

  const syncElementFromNextDocument = (selector, nextDocument) => {
    const currentElement = document.querySelector(selector);
    const nextElement = nextDocument.querySelector(selector);
    if (!currentElement || !nextElement) {
      return;
    }
    currentElement.replaceWith(nextElement.cloneNode(true));
  };

  const syncPaginationHead = (nextDocument) => {
    [
      'link[rel="canonical"]',
      'meta[name="description"]',
      'meta[property="og:url"]',
      'meta[property="og:title"]',
      'meta[property="og:description"]',
      'meta[property="og:image"]',
      'meta[name="twitter:title"]',
      'meta[name="twitter:description"]',
      'meta[name="twitter:image"]',
    ].forEach((selector) => syncElementFromNextDocument(selector, nextDocument));
  };

  const updateIndexUrl = (url, nextDocument, { pushState = true } = {}) => {
    const title = nextDocument.querySelector("title");
    if (title) {
      document.title = title.textContent || document.title;
    }
    syncPaginationHead(nextDocument);
    suppressPaginationPopstateUrl = "";
    if (pushState) {
      history.pushState({ djangoChatIndexNavigation: true }, "", url);
    }
    lastIndexUrl = new URL(url.href);
    lastPaginationUrl = `${url.pathname}${url.search}`;
  };

  const updateIndexStatus = (url, kind) => {
    const status = document.querySelector("[data-vt-pagination-status]");
    if (!status) {
      return;
    }

    status.textContent =
      kind === "filter" ? "Episode results updated." : `Episode page ${pageNumber(url)} loaded.`;
  };

  const focusPaginationResults = () => {
    const results = document.querySelector("[data-vt-results]");

    if (results instanceof HTMLElement) {
      results.focus({ preventScroll: true });
      return results;
    }

    return null;
  };

  const scrollPaginationResultsIntoView = () => {
    const results = document.querySelector("[data-vt-results]");
    if (results instanceof HTMLElement) {
      results.scrollIntoView({ block: "start", inline: "nearest" });
    }
  };

  const classifySoftIndexNavigation = (url) => {
    if (lastIndexUrl && searchWithoutPage(lastIndexUrl) !== searchWithoutPage(url)) {
      return "filter";
    }

    return "pagination";
  };

  const softNavigateIndex = async (url, { pushState = true, kind = "" } = {}) => {
    // Keep index controls as ordinary navigations when same-document transitions are unavailable.
    if (!document.startViewTransition || (reduceMotion && reduceMotion.matches)) {
      window.location.href = url.href;
      return;
    }

    if (indexNavigationController) {
      indexNavigationController.abort();
    }
    indexNavigationController = new AbortController();
    const currentResults = document.querySelector("[data-vt-results]");
    if (currentResults instanceof HTMLElement) {
      currentResults.setAttribute("aria-busy", "true");
    }
    const nextDocument = await htmlFromUrl(url.href, indexNavigationController.signal);
    const nextResults = nextDocument.querySelector("[data-vt-results]");
    if (!(currentResults instanceof HTMLElement) || !(nextResults instanceof HTMLElement)) {
      throw new Error("Index navigation response is missing episode results.");
    }

    const html = document.documentElement;
    const transitionId = indexTransitionId + 1;
    indexTransitionId = transitionId;
    let cleanupEntries = [];
    const transitionKind = kind || classifySoftIndexNavigation(url);
    if (transitionKind === "pagination") {
      html.setAttribute("data-vt-same-pagination", "true");
    }

    const namedOldResults = nameElement(currentResults, transitionNames.results);
    const previousResultsName = namedOldResults[0] ? namedOldResults[0].previousName : "";

    const viewTransition = document.startViewTransition(() => {
      cleanupEntries = replaceEpisodeResults(currentResults, nextResults, previousResultsName);
      if (replaceFilterForm(nextDocument)) {
        document.dispatchEvent(new CustomEvent("django-chat:filter-form-replaced"));
      }
      updateIndexUrl(url, nextDocument, { pushState });
      if (transitionKind === "pagination") {
        focusPaginationResults();
        scrollPaginationResultsIntoView();
      }
      updateIndexStatus(url, transitionKind);
    });

    if (transitionKind === "filter") {
      addType(viewTransition, "filter");
    }

    viewTransition.finished.finally(() => {
      if (transitionId !== indexTransitionId) {
        return;
      }
      html.removeAttribute("data-vt-same-pagination");
      restoreNamedElements(cleanupEntries);
      const results = document.querySelector("[data-vt-results]");
      if (results instanceof HTMLElement) {
        results.setAttribute("aria-busy", "false");
      }
      indexNavigationController = null;
    });
  };

  const formActionUrl = (form) => {
    const action = form.getAttribute("action") || window.location.href;
    const url = new URL(action, window.location.href);
    url.search = new URLSearchParams(new FormData(form)).toString();
    url.hash = "";
    return url;
  };

  const suppressPaginationPopstateForCurrentPage = () => {
    suppressPaginationPopstateUrl = window.location.href;
  };

  const applyTransitionHints = (viewTransition, transition) => {
    if (!transition) {
      return;
    }

    let namedElements = [];
    if (transition.kind === "filter") {
      addType(viewTransition, "filter");
      namedElements = namedElements.concat(
        nameElement(document.querySelector("[data-vt-results]"), transitionNames.results),
      );
    }

    if (transition.kind === "episode") {
      addType(viewTransition, "episode");
      namedElements = namedElements.concat(
        nameElement(findEpisodeBadge(transition.episodeSlug), transitionNames.episodeBadge),
        nameElement(findEpisodeTitle(transition.episodeSlug), transitionNames.episodeTitle),
      );
    }

    cleanAfterSnapshots(viewTransition, namedElements);
  };

  document.addEventListener(
    "click",
    (event) => {
      const link = event.target instanceof Element ? event.target.closest("a[href]") : null;
      if (!link) {
        return;
      }

      pendingEpisodeSlug = link.getAttribute("data-vt-episode-slug") || "";
      pendingFilterNavigation = false;

      if (pendingEpisodeSlug && activePage() === "episode-index") {
        rememberEpisodeIndexUrl(pendingEpisodeSlug);
      }

      if (link.getAttribute("data-vt-transition") === "filter") {
        pendingFilterNavigation = true;
        const url = new URL(link.href, window.location.href);
        if (
          isPlainNavigationClick(event, link) &&
          url.origin === window.location.origin &&
          activePage() === "episode-index"
        ) {
          event.preventDefault();
          softNavigateIndex(url, { kind: "filter" }).catch((error) => {
            if (error.name !== "AbortError") {
              const currentResults = document.querySelector("[data-vt-results]");
              if (currentResults) {
                currentResults.setAttribute("aria-busy", "false");
              }
              window.location.href = url.href;
            }
          });
        }
      }

      if (link.getAttribute("data-vt-transition") === "pagination") {
        const url = new URL(link.href, window.location.href);
        if (
          isPlainNavigationClick(event, link) &&
          url.origin === window.location.origin &&
          activePage() === "episode-index"
        ) {
          event.preventDefault();
          softNavigateIndex(url, { kind: "pagination" }).catch((error) => {
            if (error.name !== "AbortError") {
              const currentResults = document.querySelector("[data-vt-results]");
              if (currentResults) {
                currentResults.setAttribute("aria-busy", "false");
              }
              window.location.href = url.href;
            }
          });
        }
      }
    },
    { capture: true },
  );

  document.addEventListener(
    "submit",
    (event) => {
      const form = event.target;
      if (form instanceof HTMLFormElement && form.getAttribute("data-vt-transition") === "filter") {
        pendingFilterNavigation = true;
        if (activePage() === "episode-index") {
          event.preventDefault();
          const url = formActionUrl(form);
          if (url.origin !== window.location.origin) {
            window.location.href = url.href;
            return;
          }
          softNavigateIndex(url, { kind: "filter" }).catch((error) => {
            if (error.name !== "AbortError") {
              const currentResults = document.querySelector("[data-vt-results]");
              if (currentResults) {
                currentResults.setAttribute("aria-busy", "false");
              }
              window.location.href = url.href;
            }
          });
        }
      }
    },
    { capture: true },
  );

  window.addEventListener("pageswap", (event) => {
    if (!event.viewTransition) {
      return;
    }

    const fromUrl = new URL(window.location.href);
    const toUrl = getActivationUrl(event.activation);
    if (!toUrl) {
      return;
    }

    applyTransitionHints(event.viewTransition, classifyBeforeNavigation(fromUrl, toUrl));
  });

  window.addEventListener("pagereveal", (event) => {
    initPage();

    if (!event.viewTransition) {
      return;
    }

    const activation = event.activation || (window.navigation && window.navigation.activation);
    const fromUrl = getPreviousUrl(activation);
    if (!fromUrl) {
      return;
    }

    const currentUrl = new URL(window.location.href);
    if (activePage() === "episode-index" && fromUrl.pathname !== currentUrl.pathname) {
      suppressPaginationPopstateForCurrentPage();
    }

    applyTransitionHints(event.viewTransition, classifyAfterNavigation(fromUrl, currentUrl));
  });

  window.addEventListener("popstate", () => {
    if (activePage() !== "episode-index" || !document.querySelector("[data-vt-results]")) {
      return;
    }
    const currentPathSearch = `${window.location.pathname}${window.location.search}`;
    if (currentPathSearch === lastPaginationUrl) {
      // Hash-only change (in-page anchor) — let the browser handle scrolling.
      return;
    }
    lastPaginationUrl = currentPathSearch;
    if (suppressPaginationPopstateUrl) {
      const shouldSuppress = suppressPaginationPopstateUrl === window.location.href;
      suppressPaginationPopstateUrl = "";
      if (shouldSuppress) {
        return;
      }
    }

    const url = new URL(window.location.href);
    softNavigateIndex(url, {
      pushState: false,
      kind: classifySoftIndexNavigation(url),
    }).catch((error) => {
      if (error.name !== "AbortError") {
        const currentResults = document.querySelector("[data-vt-results]");
        if (currentResults) {
          currentResults.setAttribute("aria-busy", "false");
        }
        window.location.reload();
      }
    });
  });

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initPage, { once: true });
  } else {
    initPage();
  }
})();
