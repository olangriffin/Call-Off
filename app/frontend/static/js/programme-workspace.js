(() => {
  document.querySelectorAll("[data-programme-workspace]").forEach((workspace) => {
    const rows = Array.from(workspace.querySelectorAll("[data-programme-row]"));
    const search = workspace.querySelector("[data-programme-search]");
    const status = workspace.querySelector("[data-programme-status]");
    const packageFilter = workspace.querySelector("[data-programme-package]");
    const clear = workspace.querySelector("[data-programme-clear]");
    const results = workspace.querySelector("[data-programme-results]");
    const empty = workspace.querySelector("[data-programme-empty]");
    const scrollArea = workspace.querySelector("[data-programme-scroll]");
    const todayButton = workspace.querySelector("[data-programme-today]");
    const viewButtons = Array.from(
      workspace.querySelectorAll("[data-programme-view]"),
    );
    const compactViewport = window.matchMedia("(max-width: 1000px)");
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

    function applyFilters() {
      const query = search?.value.trim().toLowerCase() || "";
      const selectedStatus = status?.value || "";
      const selectedPackage = packageFilter?.value || "";
      const filtersActive = Boolean(query || selectedStatus || selectedPackage);
      const matchingRows = new Set();
      const visibleActivityIds = new Set();
      const rowsByActivityId = new Map(
        rows.map((row) => [row.dataset.activityId, row]),
      );

      rows.forEach((row) => {
        const matches =
          (!query || row.dataset.search?.includes(query)) &&
          (!selectedStatus || row.dataset.status === selectedStatus) &&
          (!selectedPackage || row.dataset.package === selectedPackage);

        if (matches) {
          matchingRows.add(row);
          visibleActivityIds.add(row.dataset.activityId);
        }
      });

      if (filtersActive) {
        matchingRows.forEach((row) => {
          let parentId = row.dataset.parentId;

          while (parentId) {
            visibleActivityIds.add(parentId);
            parentId = rowsByActivityId.get(parentId)?.dataset.parentId;
          }
        });
      }

      rows.forEach((row) => {
        const isVisible = visibleActivityIds.has(row.dataset.activityId);
        row.hidden = !isVisible;
        row.classList.toggle(
          "is-filter-context",
          filtersActive && isVisible && !matchingRows.has(row),
        );
      });

      const matchCount = matchingRows.size;
      const visibleCount = rows.filter((row) => !row.hidden).length;

      if (results) {
        results.textContent =
          matchCount === rows.length
            ? `Showing all ${rows.length} activities.`
            : visibleCount === matchCount
              ? `Showing ${matchCount} of ${rows.length} activities.`
              : `Showing ${matchCount} matches with their parent activities.`;
      }

      if (empty) empty.hidden = matchCount !== 0;
      if (scrollArea) scrollArea.hidden = matchCount === 0;
      if (todayButton) todayButton.disabled = matchCount === 0;
    }

    function setView(view) {
      workspace.dataset.view = view;
      viewButtons.forEach((button) => {
        button.setAttribute(
          "aria-pressed",
          String(button.dataset.programmeView === view),
        );
      });
    }

    search?.addEventListener("input", applyFilters);
    status?.addEventListener("change", applyFilters);
    packageFilter?.addEventListener("change", applyFilters);
    clear?.addEventListener("click", () => {
      if (search) search.value = "";
      if (status) status.value = "";
      if (packageFilter) packageFilter.value = "";
      applyFilters();
      search?.focus();
    });

    viewButtons.forEach((button) => {
      button.addEventListener("click", () => {
        setView(button.dataset.programmeView || "list");
      });
    });

    todayButton?.addEventListener("click", () => {
      const marker = workspace.querySelector("[data-today-marker]");
      const timelineCell = marker?.closest(".programme-timeline-column");

      if (!marker || !timelineCell || !scrollArea) return;

      const target =
        timelineCell.offsetLeft + marker.offsetLeft - scrollArea.clientWidth / 2;
      scrollArea.scrollTo({
        left: Math.max(target, 0),
        behavior: reducedMotion.matches ? "auto" : "smooth",
      });
      scrollArea.focus({ preventScroll: true });
    });

    function setResponsiveDefault(event) {
      if (event.matches) {
        setView("list");
      } else {
        setView("combined");
      }
    }

    compactViewport.addEventListener("change", setResponsiveDefault);
    setResponsiveDefault(compactViewport);
    applyFilters();
  });
})();
