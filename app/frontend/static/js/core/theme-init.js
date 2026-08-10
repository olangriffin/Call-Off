(() => {
  // Applies the stored/system theme to <html> before first paint, on every
  // page - including ones like the login screen that render without a nav
  // and therefore without a #theme-toggle button. core/theme-toggle.js only
  // wires up that button when one exists; it relies on this having already
  // run. Kept as an external file (not an inline <script>) because the
  // app's CSP has no 'unsafe-inline' in script-src.
  const stored = localStorage.getItem("calloff-theme");
  const theme =
    stored ||
    (window.matchMedia("(prefers-color-scheme: dark)").matches
      ? "dark"
      : "light");

  document.documentElement.dataset.theme = theme;
})();
