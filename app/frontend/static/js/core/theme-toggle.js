(() => {
  const root = document.documentElement;
  const toggle = document.getElementById("theme-toggle");
  const favicon = document.getElementById("site-favicon");

  function applyTheme(theme) {
    const isDark = theme === "dark";

    root.dataset.theme = theme;

    if (favicon) {
      const href = isDark ? favicon.dataset.darkHref : favicon.dataset.lightHref;
      if (href) favicon.setAttribute("href", href);
    }

    if (!toggle) return;

    toggle.setAttribute("aria-pressed", String(isDark));
    toggle.setAttribute(
      "aria-label",
      isDark ? "Switch to light mode" : "Switch to dark mode",
    );
  }

  // core/theme-init.js (loaded in <head>, before first paint) has already
  // set root.dataset.theme - this just syncs this page's controls to match it.
  applyTheme(root.dataset.theme === "dark" ? "dark" : "light");

  if (!toggle) return;

  toggle.addEventListener("click", () => {
    const nextTheme = root.dataset.theme === "dark" ? "light" : "dark";

    applyTheme(nextTheme);
    localStorage.setItem("calloff-theme", nextTheme);
  });
})();
