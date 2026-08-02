(() => {
  const menu = document.querySelector(".marketing-nav-menu");
  const toggle = document.querySelector(".marketing-nav-menu-toggle");
  const panel = document.getElementById("marketing-nav-menu-panel");
  const collapsedNavigation = window.matchMedia("(max-width: 1050px)");

  if (!menu || !toggle || !panel) return;

  function setOpen(isOpen) {
    menu.classList.toggle("is-open", isOpen);
    toggle.setAttribute("aria-expanded", String(isOpen));
    toggle.setAttribute(
      "aria-label",
      isOpen ? "Close navigation actions" : "Open navigation actions",
    );

    if (collapsedNavigation.matches) {
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

  collapsedNavigation.addEventListener("change", () => setOpen(false));
  setOpen(false);
})();
