(() => {
  const form = document.querySelector("[data-early-access-form]");

  if (!form) return;

  const submitButton = form.querySelector("[data-submit-button]");
  const submitLabel = form.querySelector("[data-submit-label]");
  let isSubmitting = false;

  function fieldErrorElement(field) {
    const describedBy = field.getAttribute("aria-describedby");

    if (!describedBy) return null;

    return document.getElementById(describedBy);
  }

  function messageForField(field) {
    if (field.validity.valueMissing) {
      return "This field is required.";
    }

    if (field.validity.typeMismatch && field.type === "email") {
      return "Enter a valid work email address.";
    }

    if (field.validity.tooLong) {
      return `Use ${field.maxLength} characters or fewer.`;
    }

    return "";
  }

  function validateField(field) {
    if (
      !(
        field instanceof HTMLInputElement ||
        field instanceof HTMLSelectElement ||
        field instanceof HTMLTextAreaElement
      )
    ) {
      return true;
    }

    if (field.type === "hidden" || field.name === "website") {
      return true;
    }

    if (field.name === "interest_level") {
      const group = form.querySelector('fieldset [name="interest_level"]')?.closest(
        "fieldset",
      );
      const error = document.getElementById("interest_level_error");
      const valid = Boolean(
        form.querySelector('[name="interest_level"]:checked'),
      );

      group?.setAttribute("aria-invalid", valid ? "false" : "true");
      if (error) error.textContent = valid ? "" : "Choose an interest level.";
      return valid;
    }

    const error = fieldErrorElement(field);
    const message = messageForField(field);

    field.setAttribute("aria-invalid", message ? "true" : "false");

    if (error) {
      error.textContent = message;
    }

    return !message;
  }

  form.addEventListener("input", (event) => {
    validateField(event.target);
  });

  form.addEventListener("change", (event) => {
    validateField(event.target);
  });

  form.addEventListener("submit", (event) => {
    const fields = Array.from(
      form.querySelectorAll("input, select, textarea"),
    );
    const validationResults = fields.map(validateField);
    const isValid = validationResults.every(Boolean);

    if (!isValid) {
      event.preventDefault();
      form.querySelector('[aria-invalid="true"]')?.focus();
      return;
    }

    if (isSubmitting) {
      event.preventDefault();
      return;
    }

    isSubmitting = true;

    if (submitButton) {
      submitButton.disabled = true;
      submitButton.setAttribute("aria-busy", "true");
    }

    if (submitLabel) {
      submitLabel.textContent = "Submitting...";
    }
  });
})();
