/*
 * Progressive enhancement for the show-note icon picker (Wagtail admin only).
 *
 * When "Automatisch" is the intent, this shows a LIVE preview of the icon that
 * the auto rules would derive from the current heading text. It mirrors the
 * small matcher from django_chat/imports/show_notes.py::resolve_icon_kind; the
 * rule DATA (label map, keywords) comes from the server via data-attributes, and
 * the SVGs are cloned from the already-rendered manual tiles (no duplication).
 *
 * Core editing works without this file — it only swaps a decorative preview.
 */
(function () {
  "use strict";

  // Mirror of show_notes._section_label_key: collapse whitespace, drop a single
  // trailing colon, casefold, then strip leading non-alphanumeric characters.
  function sectionLabelKey(value) {
    var label = (value || "").trim().replace(/\s+/g, " ");
    if (label.slice(-1) === ":") label = label.slice(0, -1);
    label = label.toLowerCase();
    while (label && !/[\p{L}\p{N}]/u.test(label[0])) {
      label = label.slice(1).replace(/^\s+/, "");
    }
    return label;
  }

  // Mirror of show_notes.resolve_icon_kind.
  function resolveIconKind(heading, data) {
    heading = heading || "";
    var key = sectionLabelKey(heading);
    if (Object.prototype.hasOwnProperty.call(data.labels, key)) {
      return data.labels[key];
    }
    var folded = heading.toLowerCase();
    var hasSaleWord = data.saleKeywords.some(function (kw) {
      return new RegExp("\\b" + kw + "\\b").test(folded);
    });
    if (heading.indexOf("%") !== -1 || hasSaleWord) return "sale";
    if (data.dashboardKeyword && folded.indexOf(data.dashboardKeyword) !== -1) {
      return "dashboards";
    }
    return "default";
  }

  function parseData(root) {
    function attr(name, fallback) {
      var raw = root.getAttribute(name);
      if (!raw) return fallback;
      try {
        return JSON.parse(raw);
      } catch (e) {
        return fallback;
      }
    }
    return {
      labels: attr("data-resolve-labels", {}),
      saleKeywords: attr("data-sale-keywords", []),
      dashboardKeyword: root.getAttribute("data-dashboard-keyword") || "dashboard",
    };
  }

  function findHeadingInput(root) {
    // Wagtail wraps each StructBlock child in [data-contentpath="<name>"].
    var kindWrap = root.closest("[data-contentpath]");
    var scope = kindWrap && kindWrap.parentElement ? kindWrap.parentElement : null;
    if (scope) {
      var wrap = scope.querySelector('[data-contentpath="heading"]');
      var input = wrap && wrap.querySelector("input, textarea");
      if (input) return input;
    }
    // Fallback: derive the heading field name from the kind radio name.
    var radio = root.querySelector('input[type="radio"]');
    if (radio && radio.name) {
      var headingName = radio.name.replace(/kind$/, "heading");
      var byName = document.getElementsByName(headingName);
      if (byName.length) return byName[0];
    }
    return null;
  }

  function tileFor(root, kind) {
    var input = root.querySelector(
      '.icon-choice__grid input[value="' + (window.CSS && CSS.escape ? CSS.escape(kind) : kind) + '"]'
    );
    return input ? input.closest(".icon-choice__tile") : null;
  }

  function update(root, data, headingInput) {
    var preview = root.querySelector("[data-auto-preview]");
    if (!preview) return;
    var fallback = root.querySelector("[data-auto-fallback]");
    var kind = resolveIconKind(headingInput ? headingInput.value : "", data);
    var tile = tileFor(root, kind);
    var badge = tile && tile.querySelector(".icon-choice__icon .show-note-icon");
    if (badge) {
      preview.innerHTML = badge.outerHTML;
      preview.hidden = false;
      if (fallback) fallback.hidden = true;
    }
    var suffix = root.querySelector("[data-auto-suffix]");
    var label = tile && tile.querySelector(".icon-choice__label");
    if (suffix) suffix.textContent = label ? " → " + label.textContent.trim() : "";
  }

  function debounce(fn, ms) {
    var t;
    return function () {
      clearTimeout(t);
      t = setTimeout(fn, ms);
    };
  }

  function init(root) {
    if (root.dataset.iconChoiceReady) return;
    root.dataset.iconChoiceReady = "1";
    var data = parseData(root);
    var headingInput = findHeadingInput(root);
    var run = function () {
      update(root, data, headingInput);
    };
    if (headingInput) {
      headingInput.addEventListener("input", debounce(run, 150));
      headingInput.addEventListener("change", run);
    }
    run();
  }

  function initAll(scope) {
    (scope || document).querySelectorAll("[data-icon-choice]").forEach(init);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      initAll(document);
    });
  } else {
    initAll(document);
  }

  // StreamField inserts blocks dynamically; pick those up too.
  if (typeof MutationObserver !== "undefined") {
    var observer = new MutationObserver(function (mutations) {
      mutations.forEach(function (m) {
        m.addedNodes.forEach(function (node) {
          if (node.nodeType !== 1) return;
          if (node.matches && node.matches("[data-icon-choice]")) init(node);
          if (node.querySelectorAll) initAll(node);
        });
      });
    });
    observer.observe(document.documentElement, { childList: true, subtree: true });
  }
})();
