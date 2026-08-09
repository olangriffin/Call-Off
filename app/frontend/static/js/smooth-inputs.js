(() => {
  const TEXT_INPUT_TYPES = new Set([
    "email",
    "password",
    "search",
    "tel",
    "text",
    "url",
  ]);
  const BULLET = "•";
  const prefersReducedMotion = window.matchMedia(
    "(prefers-reduced-motion: reduce)",
  ).matches;
  const instances = new Set();

  function isEligibleInput(input) {
    if (!(input instanceof HTMLInputElement)) return false;
    if (input.dataset.smoothInput === "false") return false;

    const type = input.type || "text";

    return TEXT_INPUT_TYPES.has(type);
  }

  function copiedText(input) {
    const value = input.value || "";
    const caretIndex = input.selectionStart ?? value.length;
    const beforeCaret = value.slice(0, caretIndex);

    if (input.type === "password") {
      return BULLET.repeat(beforeCaret.length);
    }

    return beforeCaret;
  }

  function syncMirrorStyles(input, mirror) {
    const style = window.getComputedStyle(input);
    const properties = [
      "borderLeftWidth",
      "fontFamily",
      "fontSize",
      "fontStyle",
      "fontVariant",
      "fontWeight",
      "letterSpacing",
      "lineHeight",
      "paddingLeft",
      "textTransform",
    ];

    properties.forEach((property) => {
      mirror.style[property] = style[property];
    });
  }

  function shouldShowCaret(input) {
    if (document.activeElement !== input) return false;
    if (input.selectionStart === null || input.selectionEnd === null)
      return true;

    return input.selectionStart === input.selectionEnd;
  }

  function createSmoothInput(input) {
    if (
      prefersReducedMotion ||
      !isEligibleInput(input) ||
      input.closest(".smooth-input-shell")
    ) {
      return;
    }

    const shell = document.createElement("span");
    const mirror = document.createElement("span");
    const mirrorText = document.createElement("span");
    const caret = document.createElement("span");

    shell.className = "smooth-input-shell";
    mirror.className = "smooth-input-mirror";
    caret.className = "smooth-input-caret";

    input.parentNode?.insertBefore(shell, input);
    shell.append(input, mirror, caret);
    mirror.append(mirrorText);
    input.classList.add("smooth-caret-input");

    const instance = {
      animationFrame: 0,
      caret,
      input,
      mirror,
      mirrorText,
    };

    instances.add(instance);

    function targetPosition() {
      syncMirrorStyles(input, mirror);
      mirrorText.textContent = copiedText(input);

      const mirrorRect = mirror.getBoundingClientRect();
      const textRect = mirrorText.getBoundingClientRect();
      const inputStyle = window.getComputedStyle(input);
      const paddingRight = parseFloat(inputStyle.paddingRight) || 0;
      const maxX = input.clientWidth - paddingRight;
      const x = textRect.right - mirrorRect.left - input.scrollLeft;

      return Math.max(0, Math.min(maxX, x));
    }

    function render() {
      const nextX = targetPosition();
      const visible = shouldShowCaret(input);

      caret.style.transform = `translate3d(${nextX}px, -50%, 0)`;
      caret.style.opacity = visible ? "1" : "0";
      instance.animationFrame = 0;
    }

    function update() {
      if (!instance.animationFrame) {
        instance.animationFrame = requestAnimationFrame(render);
      }
    }

    input.addEventListener("focus", update);
    input.addEventListener("blur", update);
    input.addEventListener("input", update);
    input.addEventListener("keydown", update);
    input.addEventListener("keyup", update);
    input.addEventListener("select", update);
    input.addEventListener("click", update);
    input.addEventListener("scroll", update);

    if ("ResizeObserver" in window) {
      new ResizeObserver(update).observe(input);
    }

    update();
  }

  function initialiseSmoothInputs(root = document) {
    if (root instanceof HTMLInputElement) {
      createSmoothInput(root);
      return;
    }

    root.querySelectorAll("input").forEach(createSmoothInput);
  }

  document.addEventListener("selectionchange", () => {
    instances.forEach((instance) => {
      if (document.activeElement === instance.input) {
        const event = new Event("select");
        instance.input.dispatchEvent(event);
      }
    });
  });

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () =>
      initialiseSmoothInputs(),
    );
  } else {
    initialiseSmoothInputs();
  }

  new MutationObserver((mutations) => {
    mutations.forEach((mutation) => {
      mutation.addedNodes.forEach((node) => {
        if (node instanceof Element) {
          initialiseSmoothInputs(node);
        }
      });
    });
  }).observe(document.documentElement, {
    childList: true,
    subtree: true,
  });
})();
