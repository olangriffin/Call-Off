(() => {
  const root = document.documentElement;
  const toggle = document.getElementById("theme-toggle");

  if (!toggle) return;

  const storedTheme = localStorage.getItem("calloff-theme");
  const systemPrefersDark = window.matchMedia(
    "(prefers-color-scheme: dark)",
  ).matches;

  const initialTheme = storedTheme || (systemPrefersDark ? "dark" : "light");

  function applyTheme(theme) {
    const isDark = theme === "dark";

    root.dataset.theme = theme;
    toggle.setAttribute("aria-pressed", String(isDark));
    toggle.setAttribute(
      "aria-label",
      isDark ? "Switch to light mode" : "Switch to dark mode",
    );
  }

  applyTheme(initialTheme);

  toggle.addEventListener("click", () => {
    const nextTheme = root.dataset.theme === "dark" ? "light" : "dark";

    applyTheme(nextTheme);
    localStorage.setItem("calloff-theme", nextTheme);
  });
})();
