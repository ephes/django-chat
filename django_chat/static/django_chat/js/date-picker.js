(() => {
  let activeFilterForm = null;
  let popoverCounter = 0;
  const pad = (value) => String(value).padStart(2, "0");

  const nextPopoverId = (prefix) => {
    popoverCounter += 1;
    return `dc-${prefix}-${popoverCounter}`;
  };

  const parseDateValue = (value) => {
    const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
    if (!match) {
      return null;
    }

    const year = Number(match[1]);
    const month = Number(match[2]) - 1;
    const day = Number(match[3]);
    const date = new Date(year, month, day);

    if (date.getFullYear() !== year || date.getMonth() !== month || date.getDate() !== day) {
      return null;
    }

    return date;
  };

  const isoDate = (date) =>
    `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;

  const displayDate = (value) => {
    const date = parseDateValue(value);
    return date ? `${pad(date.getDate())}.${pad(date.getMonth() + 1)}.${date.getFullYear()}` : "";
  };

  const monthTitle = (date) =>
    date.toLocaleDateString("en", {
      month: "long",
      year: "numeric",
    });

  const closeOpenPopovers = (except = null) => {
    if (!activeFilterForm) {
      return;
    }

    activeFilterForm.querySelectorAll("[data-filter-popover].is-open").forEach((popover) => {
      if (popover !== except) {
        popover.classList.remove("is-open");
        const button = popover.parentElement?.querySelector("[aria-expanded='true']");
        button?.setAttribute("aria-expanded", "false");
      }
    });
  };

  const concealNativeControl = (control) => {
    control.classList.add("filter-native-control");
    control.tabIndex = -1;
    control.setAttribute("aria-hidden", "true");
  };

  const alignPopover = (popover) => {
    popover.classList.remove("filter-popover--align-right");

    const margin = 16;
    const rect = popover.getBoundingClientRect();
    if (rect.right > window.innerWidth - margin) {
      popover.classList.add("filter-popover--align-right");
    }
  };

  const closeWhenFocusLeaves = (field) => {
    field.addEventListener("focusout", () => {
      window.setTimeout(() => {
        const popover = field.querySelector("[data-filter-popover]");
        const button = field.querySelector("[aria-expanded='true']");
        if (popover?.classList.contains("is-open") && !field.contains(document.activeElement)) {
          popover.classList.remove("is-open");
          button?.setAttribute("aria-expanded", "false");
        }
      }, 0);
    });
  };

  const sameDayInMonth = (date, monthDelta) => {
    const targetYear = date.getFullYear();
    const targetMonth = date.getMonth() + monthDelta;
    const daysInTargetMonth = new Date(targetYear, targetMonth + 1, 0).getDate();
    return new Date(targetYear, targetMonth, Math.min(date.getDate(), daysInTargetMonth));
  };

  const enhanceDateInput = (input) => {
    if (!(input instanceof HTMLInputElement) || input.type !== "date") {
      return;
    }

    const field = document.createElement("span");
    field.className = "filter-control filter-date-control";

    const button = document.createElement("button");
    button.type = "button";
    button.className = "filter-control-button filter-date-button";
    button.setAttribute("aria-label", input.id === "id_date_0" ? "Start date" : "End date");
    button.setAttribute("aria-haspopup", "dialog");
    button.setAttribute("aria-expanded", "false");

    const text = document.createElement("span");
    text.className = "filter-control-text";

    const icon = document.createElement("span");
    icon.className = "filter-calendar-icon";
    icon.setAttribute("aria-hidden", "true");

    button.append(text, icon);

    const popover = document.createElement("div");
    popover.className = "filter-popover filter-date-popover";
    popover.id = nextPopoverId("date-popover");
    popover.setAttribute("data-filter-popover", "");
    popover.setAttribute("role", "dialog");
    popover.setAttribute("aria-label", input.id === "id_date_0" ? "Choose start date" : "Choose end date");
    button.setAttribute("aria-controls", popover.id);

    let viewDate = parseDateValue(input.value) || new Date();
    viewDate = new Date(viewDate.getFullYear(), viewDate.getMonth(), 1);

    const syncButton = () => {
      text.textContent = displayDate(input.value) || "dd.mm.yyyy";
      button.classList.toggle("is-empty", !input.value);
    };

    const focusDate = (date) => {
      const value = isoDate(date);
      if (viewDate.getFullYear() !== date.getFullYear() || viewDate.getMonth() !== date.getMonth()) {
        viewDate = new Date(date.getFullYear(), date.getMonth(), 1);
        renderCalendar();
      }

      const target = popover.querySelector(`[data-date="${value}"]`);
      if (!(target instanceof HTMLButtonElement)) {
        return;
      }

      popover.querySelectorAll(".filter-date-day").forEach((day) => {
        if (day instanceof HTMLButtonElement) {
          day.tabIndex = -1;
        }
      });
      target.tabIndex = 0;
      target.focus();
    };

    const firstOfVisibleMonth = () => new Date(viewDate.getFullYear(), viewDate.getMonth(), 1);

    const focusInitialDate = () => {
      const selected = parseDateValue(input.value);
      focusDate(selected || new Date());
    };

    const setValue = (date) => {
      input.value = isoDate(date);
      input.dispatchEvent(new Event("input", { bubbles: true }));
      input.dispatchEvent(new Event("change", { bubbles: true }));
      syncButton();
      closeOpenPopovers();
      button.focus();
    };

    const renderCalendar = () => {
      const selected = parseDateValue(input.value);
      const todayIso = isoDate(new Date());
      const month = viewDate.getMonth();
      const firstWeekday = (viewDate.getDay() + 6) % 7;
      const firstVisible = new Date(viewDate.getFullYear(), month, 1 - firstWeekday);
      const weeks = 6;

      popover.replaceChildren();

      const header = document.createElement("div");
      header.className = "filter-date-popover-header";

      const previous = document.createElement("button");
      previous.type = "button";
      previous.className = "filter-popover-icon-button";
      previous.setAttribute("aria-label", "Previous month");
      previous.textContent = "<";

      const title = document.createElement("strong");
      title.textContent = monthTitle(viewDate);

      const next = document.createElement("button");
      next.type = "button";
      next.className = "filter-popover-icon-button";
      next.setAttribute("aria-label", "Next month");
      next.textContent = ">";

      const moveMonth = (event, monthDelta) => {
        // Rerendering detaches event.target before the document click handler
        // can check whether the click happened inside the filter form.
        event.stopPropagation();
        viewDate = new Date(viewDate.getFullYear(), viewDate.getMonth() + monthDelta, 1);
        renderCalendar();
        focusDate(firstOfVisibleMonth());
      };

      previous.addEventListener("click", (event) => moveMonth(event, -1));
      next.addEventListener("click", (event) => moveMonth(event, 1));

      header.append(previous, title, next);
      popover.append(header);

      const weekdays = document.createElement("div");
      weekdays.className = "filter-date-weekdays";
      ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"].forEach((weekday) => {
        const label = document.createElement("span");
        label.textContent = weekday;
        weekdays.append(label);
      });
      popover.append(weekdays);

      const grid = document.createElement("div");
      grid.className = "filter-date-grid";

      for (let index = 0; index < weeks * 7; index += 1) {
        const date = new Date(firstVisible);
        date.setDate(firstVisible.getDate() + index);
        const value = isoDate(date);
        const day = document.createElement("button");
        day.type = "button";
        day.className = "filter-date-day";
        day.textContent = String(date.getDate());
        day.tabIndex = -1;
        day.dataset.date = value;
        const dayLabelParts = [
          date.toLocaleDateString("en", {
            day: "numeric",
            month: "long",
            year: "numeric",
          }),
        ];
        if (selected && value === isoDate(selected)) {
          dayLabelParts.push("selected");
        }
        if (value === todayIso) {
          dayLabelParts.push("today");
        }
        day.setAttribute("aria-label", dayLabelParts.join(", "));

        if (date.getMonth() !== month) {
          day.classList.add("is-outside-month");
        }
        if (selected && value === isoDate(selected)) {
          day.classList.add("is-selected");
        }
        if (value === todayIso) {
          day.classList.add("is-today");
          day.setAttribute("aria-current", "date");
        }

        day.addEventListener("click", () => setValue(date));
        day.addEventListener("keydown", (event) => {
          const activeDate = parseDateValue(day.dataset.date || "");
          if (!activeDate) {
            return;
          }

          let nextDate = null;
          if (event.key === "ArrowLeft") {
            nextDate = new Date(activeDate);
            nextDate.setDate(activeDate.getDate() - 1);
          } else if (event.key === "ArrowRight") {
            nextDate = new Date(activeDate);
            nextDate.setDate(activeDate.getDate() + 1);
          } else if (event.key === "ArrowUp") {
            nextDate = new Date(activeDate);
            nextDate.setDate(activeDate.getDate() - 7);
          } else if (event.key === "ArrowDown") {
            nextDate = new Date(activeDate);
            nextDate.setDate(activeDate.getDate() + 7);
          } else if (event.key === "Home") {
            nextDate = new Date(activeDate);
            nextDate.setDate(activeDate.getDate() - ((activeDate.getDay() + 6) % 7));
          } else if (event.key === "End") {
            nextDate = new Date(activeDate);
            nextDate.setDate(activeDate.getDate() + (6 - ((activeDate.getDay() + 6) % 7)));
          } else if (event.key === "PageUp") {
            nextDate = sameDayInMonth(activeDate, -1);
          } else if (event.key === "PageDown") {
            nextDate = sameDayInMonth(activeDate, 1);
          } else if (event.key === "Escape") {
            closeOpenPopovers();
            button.focus();
            return;
          }

          if (nextDate) {
            event.preventDefault();
            focusDate(nextDate);
          }
        });
        grid.append(day);
      }

      const actions = document.createElement("div");
      actions.className = "filter-date-actions";

      const clear = document.createElement("button");
      clear.type = "button";
      clear.textContent = "Clear";
      clear.addEventListener("click", () => {
        input.value = "";
        input.dispatchEvent(new Event("input", { bubbles: true }));
        input.dispatchEvent(new Event("change", { bubbles: true }));
        syncButton();
        closeOpenPopovers();
        button.focus();
      });

      const today = document.createElement("button");
      today.type = "button";
      today.textContent = "Today";
      today.addEventListener("click", () => setValue(new Date()));

      actions.append(clear, today);
      popover.append(grid, actions);
    };

    button.addEventListener("click", () => {
      const willOpen = !popover.classList.contains("is-open");
      closeOpenPopovers(popover);
      popover.classList.toggle("is-open", willOpen);
      button.setAttribute("aria-expanded", String(willOpen));
      if (willOpen) {
        const selected = parseDateValue(input.value) || new Date();
        viewDate = new Date(selected.getFullYear(), selected.getMonth(), 1);
        renderCalendar();
        alignPopover(popover);
        focusInitialDate();
      }
    });

    concealNativeControl(input);
    closeWhenFocusLeaves(field);
    input.after(field);
    field.append(input, button, popover);
    syncButton();
  };

  const enhanceSelect = (select) => {
    if (!(select instanceof HTMLSelectElement)) {
      return;
    }

    const field = document.createElement("span");
    field.className = "filter-control filter-select-control";

    const button = document.createElement("button");
    button.type = "button";
    button.className = "filter-control-button filter-select-button";
    if (select.getAttribute("aria-label")) {
      button.setAttribute("aria-label", select.getAttribute("aria-label"));
    }
    button.setAttribute("aria-haspopup", "dialog");
    button.setAttribute("aria-expanded", "false");

    const text = document.createElement("span");
    text.className = "filter-control-text";

    const icon = document.createElement("span");
    icon.className = "filter-select-icon";
    icon.setAttribute("aria-hidden", "true");

    button.append(text, icon);

    const popover = document.createElement("div");
    popover.className = "filter-popover filter-select-popover";
    popover.id = nextPopoverId("select-popover");
    popover.setAttribute("data-filter-popover", "");
    popover.setAttribute("role", "dialog");
    if (select.getAttribute("aria-label")) {
      popover.setAttribute("aria-label", select.getAttribute("aria-label"));
    }
    button.setAttribute("aria-controls", popover.id);

    const optionLabel = (option) => option.textContent?.trim() || option.value || "Select";

    const syncButton = () => {
      text.textContent = optionLabel(select.selectedOptions[0] || select.options[0]);
    };

    const selectOption = (option) => {
      select.value = option.value;
      select.dispatchEvent(new Event("input", { bubbles: true }));
      select.dispatchEvent(new Event("change", { bubbles: true }));
      syncButton();
      closeOpenPopovers();
      button.focus();
    };

    const focusOption = (index) => {
      const items = Array.from(popover.querySelectorAll(".filter-select-option")).filter(
        (item) => item instanceof HTMLButtonElement,
      );
      if (!items.length) {
        return;
      }

      const nextIndex = Math.max(0, Math.min(items.length - 1, index));
      items.forEach((item) => {
        item.tabIndex = -1;
      });
      items[nextIndex].tabIndex = 0;
      items[nextIndex].focus();
    };

    const focusSelectedOption = () => {
      focusOption(Math.max(0, select.selectedIndex));
    };

    const renderOptions = () => {
      popover.replaceChildren();
      Array.from(select.options).forEach((option) => {
        const item = document.createElement("button");
        item.type = "button";
        item.className = "filter-select-option";
        item.tabIndex = -1;
        item.textContent = optionLabel(option);
        item.setAttribute(
          "aria-label",
          option.selected ? `${optionLabel(option)}, selected` : optionLabel(option),
        );

        if (option.selected) {
          item.classList.add("is-selected");
        }

        item.addEventListener("click", () => selectOption(option));
        item.addEventListener("keydown", (event) => {
          const items = Array.from(popover.querySelectorAll(".filter-select-option"));
          const currentIndex = items.indexOf(item);

          if (event.key === "ArrowDown") {
            event.preventDefault();
            focusOption(currentIndex + 1);
          } else if (event.key === "ArrowUp") {
            event.preventDefault();
            focusOption(currentIndex - 1);
          } else if (event.key === "Home") {
            event.preventDefault();
            focusOption(0);
          } else if (event.key === "End") {
            event.preventDefault();
            focusOption(items.length - 1);
          } else if (event.key === "Escape") {
            closeOpenPopovers();
            button.focus();
          } else if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            selectOption(option);
          }
        });

        popover.append(item);
      });
    };

    button.addEventListener("click", () => {
      const willOpen = !popover.classList.contains("is-open");
      closeOpenPopovers(popover);
      popover.classList.toggle("is-open", willOpen);
      button.setAttribute("aria-expanded", String(willOpen));
      if (willOpen) {
        renderOptions();
        alignPopover(popover);
        focusSelectedOption();
      }
    });

    concealNativeControl(select);
    closeWhenFocusLeaves(field);
    select.after(field);
    field.append(select, button, popover);
    syncButton();
  };

  const enhanceFilterForm = (filterForm) => {
    if (!(filterForm instanceof HTMLFormElement) || filterForm.hasAttribute("data-filter-enhanced")) {
      return;
    }

    filterForm.setAttribute("data-filter-enhanced", "true");
    activeFilterForm = filterForm;
    filterForm.querySelectorAll('input[type="date"]').forEach(enhanceDateInput);
    filterForm.querySelectorAll("select").forEach(enhanceSelect);
  };

  document.addEventListener("click", (event) => {
    if (event.target instanceof Node && activeFilterForm?.contains(event.target)) {
      return;
    }
    closeOpenPopovers();
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closeOpenPopovers();
    }
  });

  document.addEventListener("django-chat:filter-form-replaced", () => {
    enhanceFilterForm(document.querySelector(".filter-form"));
  });

  enhanceFilterForm(document.querySelector(".filter-form"));
})();
