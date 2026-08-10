(() => {
  // Drives any .site-nav-menu dropdown: the marketing header's mobile
  // actions menu and the app header's account menu. Both share the same
  // toggle/panel open-close mechanic; they differ only in whether the panel
  // is *always* a dropdown (no data-nav-menu-collapse-below attribute, e.g.
  // the account menu) or only becomes one below a given viewport width
  // (marketing's actions menu, which is otherwise a plain inline row).
  const menu = document.querySelector(".site-nav-menu");

  if (!menu) return;

  const toggle = menu.querySelector(".site-nav-menu-toggle");
  const panel = menu.querySelector(".site-nav-menu-panel");

  if (!toggle || !panel) return;

  const collapseBelow = menu.dataset.navMenuCollapseBelow;
  const collapsedViewport = collapseBelow
    ? window.matchMedia(`(max-width: ${collapseBelow}px)`)
    : null;

  function isCollapsed() {
    return !collapsedViewport || collapsedViewport.matches;
  }

  function setOpen(isOpen) {
    menu.classList.toggle("is-open", isOpen);
    toggle.setAttribute("aria-expanded", String(isOpen));
    toggle.setAttribute(
      "aria-label",
      isOpen
        ? toggle.dataset.openLabel || "Close menu"
        : toggle.dataset.closedLabel || "Open menu",
    );

    if (isCollapsed()) {
      panel.setAttribute("aria-hidden", String(!isOpen));
      panel.inert = !isOpen;
    } else {
      panel.removeAttribute("aria-hidden");
      panel.inert = false;
    }
  }

  toggle.addEventListener("click", () => {
    setOpen(!menu.classList.contains("is-open"));
  });

  menu.addEventListener("click", (event) => {
    if (event.target instanceof HTMLAnchorElement) {
      setOpen(false);
    }
  });

  document.addEventListener("click", (event) => {
    if (event.target instanceof Node && !menu.contains(event.target)) {
      setOpen(false);
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      setOpen(false);
      toggle.focus();
    }
  });

  collapsedViewport?.addEventListener("change", () => setOpen(false));
  setOpen(false);
})();
