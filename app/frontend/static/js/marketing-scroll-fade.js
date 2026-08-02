(() => {
  const body = document.body;

  if (!body.classList.contains("marketing")) return;

  const nav = document.querySelector(".marketing-nav");
  const bottomFadeDistance = 180;

  function updateScrollFade() {
    const navHeight = nav ? nav.getBoundingClientRect().height : 0;
    const scrollMax = Math.max(
      document.documentElement.scrollHeight - window.innerHeight,
      0,
    );
    const distanceFromBottom = Math.max(scrollMax - window.scrollY, 0);
    const bottomBlurOpacity = Math.min(distanceFromBottom / bottomFadeDistance, 1);

    body.style.setProperty("--marketing-nav-height", `${navHeight}px`);
    body.style.setProperty(
      "--marketing-bottom-blur-opacity",
      String(bottomBlurOpacity),
    );
  }

  updateScrollFade();

  if ("ResizeObserver" in window && nav) {
    new ResizeObserver(updateScrollFade).observe(nav);
  }

  window.addEventListener("resize", updateScrollFade);
  window.addEventListener("scroll", updateScrollFade, { passive: true });
})();
