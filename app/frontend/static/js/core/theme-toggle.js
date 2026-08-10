(() => {
  const root = document.documentElement;
  const toggle = document.getElementById("theme-toggle");

  if (!toggle) return;

  function applyTheme(theme) {
    const isDark = theme === "dark";

    root.dataset.theme = theme;
    toggle.setAttribute("aria-pressed", String(isDark));
    toggle.setAttribute(
      "aria-label",
      isDark ? "Switch to light mode" : "Switch to dark mode",
    );
  }

  // core/theme-init.js (loaded in <head>, before first paint) has already
  // set root.dataset.theme - this just syncs this page's toggle button to
  // match it.
  applyTheme(root.dataset.theme === "dark" ? "dark" : "light");

  toggle.addEventListener("click", () => {
    const nextTheme = root.dataset.theme === "dark" ? "light" : "dark";

    applyTheme(nextTheme);
    localStorage.setItem("calloff-theme", nextTheme);
  });
})();
