(() => {
  // Progressive enhancement for the comment form's validation UX.
  //
  // Without JS the native `required` / `type="email"` constraints gate the
  // submit with the browser's own validation bubble — that is the no-JS
  // fallback, so an empty comment can never be posted either way.
  //
  // With JS we suppress that unstyled bubble (`novalidate`) and instead render
  // the browser's *own* localized validation text (`field.validationMessage`)
  // into the site's styled `.js-errors` markup — same span ajaxcomments.js
  // uses, so the `.comment-field:has(.js-errors)` red-border rule applies too.
  // We intercept submit in the capture phase BEFORE ajaxcomments.js (loaded
  // after us) so an invalid form never fires an AJAX request.
  const forms = document.querySelectorAll("form.js-comments-form");
  if (!forms.length) return;

  forms.forEach((form) => form.setAttribute("novalidate", ""));

  // Field- and constraint-specific copy, so the message names what is wrong in
  // this field ("Please enter your name.") instead of the browser's generic
  // "Please fill out this field." Keyed by the form field name, then by the
  // ValidityState flag; the browser's own `validationMessage` is the fallback
  // for any constraint we do not override.
  const MESSAGES = {
    name: { valueMissing: "Please enter your name." },
    email: {
      valueMissing: "Please enter your email address.",
      typeMismatch: "Please enter a valid email address.",
    },
    comment: { valueMissing: "Please enter your comment." },
  };

  const messageFor = (field) => {
    const map = MESSAGES[field.name];
    if (map) {
      for (const flag of Object.keys(map)) {
        if (field.validity[flag]) return map[flag];
      }
    }
    return field.validationMessage;
  };

  const clearError = (field) => {
    const next = field.nextElementSibling;
    if (next && next.classList.contains("js-errors")) next.remove();
  };

  const showError = (field) => {
    clearError(field);
    const span = document.createElement("span");
    span.className = "js-errors";
    span.textContent = messageFor(field);
    field.insertAdjacentElement("afterend", span);
  };

  const validatableFields = (form) =>
    Array.from(form.elements).filter((el) => el.willValidate && el.type !== "hidden");

  document.addEventListener(
    "submit",
    (event) => {
      const form = event.target;
      if (!(form instanceof HTMLFormElement)) return;
      if (!form.matches("form.js-comments-form")) return;

      const fields = validatableFields(form);
      const invalid = fields.filter((el) => !el.checkValidity());

      // Refresh messages on the fields the user already corrected too.
      fields.forEach(clearError);

      if (invalid.length) {
        // Stop ajaxcomments.js (also a capture-phase listener, registered
        // after us) from posting an invalid form.
        event.preventDefault();
        event.stopImmediatePropagation();
        invalid.forEach(showError);
        invalid[0].focus();
      }
    },
    true,
  );

  // Drop a field's error as soon as it becomes valid again while typing.
  forms.forEach((form) => {
    form.addEventListener("input", (event) => {
      const field = event.target;
      if (field && field.willValidate && field.checkValidity()) clearError(field);
    });
  });
})();
