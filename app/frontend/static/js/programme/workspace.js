(() => {
  function parseDetailMessage(detail) {
    if (!detail) return null;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      const [first] = detail;
      const message = typeof first?.msg === "string" ? first.msg : null;
      return message ? message.replace(/^Value error,\s*/, "") : null;
    }
    return null;
  }

  function collectPayload(form) {
    // `form` has no field descendants of its own — every input/select lives
    // in its own table cell and points back here via a form="" attribute.
    // FormData still picks those up correctly (part of the HTML spec).
    const data = new FormData(form);
    const activityType = String(data.get("activity_type") || "task");
    const optional = (value) => {
      const trimmed = String(value || "").trim();
      return trimmed || null;
    };

    return {
      // Left blank, the server auto-generates the next code.
      activity_code: optional(data.get("activity_code")),
      name: String(data.get("name") || "").trim(),
      activity_type: activityType,
      work_package_id: optional(data.get("work_package_id")),
      parent_activity_id: null,
      planned_start: optional(data.get("planned_start")),
      planned_finish: optional(data.get("planned_finish")),
      is_milestone: activityType === "milestone",
      status: String(data.get("status") || "not_started"),
      notes: null,
    };
  }

  function collectUpdatePayload(form) {
    // Unlike create, this deliberately omits parent_activity_id and notes
    // entirely (not even as null) — the update API only touches fields it
    // receives, so leaving a key out keeps that field untouched server-side
    // rather than blanking it out.
    const data = new FormData(form);
    const activityType = String(data.get("activity_type") || "task");
    const optional = (value) => {
      const trimmed = String(value || "").trim();
      return trimmed || null;
    };

    return {
      activity_code: String(data.get("activity_code") || "").trim(),
      name: String(data.get("name") || "").trim(),
      activity_type: activityType,
      work_package_id: optional(data.get("work_package_id")),
      status: String(data.get("status") || "not_started"),
      planned_start: optional(data.get("planned_start")),
      planned_finish: optional(data.get("planned_finish")),
      is_milestone: activityType === "milestone",
    };
  }

  function initWorkspace(workspace) {
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
    // Declared up front (rather than down by the edit wiring below) so
    // applyFilters(), which reads it, is never called before it exists.
    let activeEdit = null; // { displayRow, editRow, errorRow, errorText }

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
        // A row mid-edit stays hidden (its edit row stands in for it)
        // regardless of what the filters would otherwise show.
        if (row === activeEdit?.displayRow) return;

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

    // Inline "add activity" — a real row of per-column inputs (not a popup
    // form) that creates the activity without leaving the programme table,
    // via the JSON programme activities API.
    const addTriggers = Array.from(
      workspace.querySelectorAll("[data-programme-add-trigger]"),
    );
    const addForm = workspace.querySelector("[data-programme-add-form]");
    const addRow = workspace.querySelector("[data-programme-add-row]");
    const addSaveButton = workspace.querySelector("[data-programme-add-save]");
    const addCancel = workspace.querySelector("[data-programme-add-cancel]");
    const addErrorRow = workspace.querySelector("[data-programme-add-error-row]");
    const addErrorText = workspace.querySelector("[data-programme-add-error]");
    const emptyPanel = workspace.querySelector("[data-programme-empty-panel]");
    // The table only exists (visibly) so the add row has somewhere to live
    // when the project has no activities yet — this marker (set once at
    // render time) distinguishes that from a table with real data.
    const isEmptyWorkspace = scrollArea?.hasAttribute(
      "data-programme-table-hidden",
    );

    function showAddError(message) {
      if (!addErrorRow || !addErrorText) return;
      addErrorText.textContent = message;
      addErrorRow.hidden = false;
    }

    function hideAddError() {
      if (!addErrorRow || !addErrorText) return;
      addErrorRow.hidden = true;
      addErrorText.textContent = "";
    }

    function openAddForm() {
      closeEdit();
      if (isEmptyWorkspace) {
        if (emptyPanel) emptyPanel.hidden = true;
        if (scrollArea) scrollArea.hidden = false;
      }
      if (addRow) addRow.hidden = false;
      hideAddError();
      addRow
        ?.querySelector("[data-programme-add-first-field]")
        ?.focus();
    }

    function closeAddForm() {
      if (addRow) addRow.hidden = true;
      addForm?.reset();
      if (isEmptyWorkspace) {
        if (scrollArea) scrollArea.hidden = true;
        if (emptyPanel) emptyPanel.hidden = false;
      }
      hideAddError();
    }

    addTriggers.forEach((trigger) => {
      trigger.addEventListener("click", (event) => {
        event.preventDefault();
        openAddForm();
      });
    });

    addCancel?.addEventListener("click", () => closeAddForm());

    addForm?.addEventListener("submit", async (event) => {
      event.preventDefault();
      hideAddError();
      addSaveButton?.setAttribute("disabled", "disabled");

      try {
        const response = await fetch(
          `/projects/${workspace.dataset.projectId}/programme/activities`,
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              Accept: "application/json",
            },
            credentials: "same-origin",
            body: JSON.stringify(collectPayload(addForm)),
          },
        );

        if (!response.ok) {
          const problem = await response.json().catch(() => null);
          throw new Error(
            parseDetailMessage(problem?.detail) ||
              "Unable to create the activity. Check the fields and try again.",
          );
        }

        await refreshWorkspace(workspace, { reopenAddForm: true });
      } catch (error) {
        showAddError(
          error instanceof Error
            ? error.message
            : "Unable to create the activity. Check the fields and try again.",
        );
      } finally {
        addSaveButton?.removeAttribute("disabled");
      }
    });

    // Inline "edit activity" — a single shared row template is cloned next
    // to whichever display row is being edited, pre-filled from that row's
    // data-edit-* attributes, and PATCHed via the JSON API on save. Only one
    // edit (or the add row) is open at a time.
    const editForm = workspace.querySelector("[data-programme-edit-form]");
    const editRowTemplate = workspace.querySelector(
      "[data-programme-edit-row-template]",
    );

    function hideEditError() {
      if (!activeEdit) return;
      activeEdit.errorRow.hidden = true;
      activeEdit.errorText.textContent = "";
    }

    function showEditError(message) {
      if (!activeEdit) return;
      activeEdit.errorText.textContent = message;
      activeEdit.errorRow.hidden = false;
    }

    function closeEdit() {
      if (!activeEdit) return;
      const { editRow, errorRow } = activeEdit;
      editRow.remove();
      errorRow.remove();
      activeEdit = null;
      // Re-apply filters rather than force the row back on — if a filter
      // changed while it was being edited, it may no longer match.
      applyFilters();
    }

    function openEdit(displayRow) {
      if (!editRowTemplate || !editForm) return;
      if (activeEdit?.displayRow === displayRow) return;

      closeEdit();
      closeAddForm();

      const fragment = editRowTemplate.content.cloneNode(true);
      const editRow = fragment.querySelector("[data-programme-edit-row]");
      const errorRow = fragment.querySelector("[data-programme-edit-error-row]");
      const errorText = fragment.querySelector("[data-programme-edit-error]");

      const setValue = (name, value) => {
        const field = editRow.querySelector(`[name="${name}"]`);
        if (field) field.value = value;
      };

      setValue("activity_code", displayRow.dataset.editCode || "");
      setValue("name", displayRow.dataset.editName || "");
      setValue("activity_type", displayRow.dataset.editType || "task");
      setValue("work_package_id", displayRow.dataset.editWorkPackageId || "");
      setValue("status", displayRow.dataset.editStatus || "not_started");
      setValue("planned_start", displayRow.dataset.editStart || "");
      setValue("planned_finish", displayRow.dataset.editFinish || "");

      // afterend twice, in this order, lands as: displayRow, editRow, errorRow.
      displayRow.insertAdjacentElement("afterend", errorRow);
      displayRow.insertAdjacentElement("afterend", editRow);
      displayRow.hidden = true;

      activeEdit = {
        displayRow,
        editRow,
        errorRow,
        errorText,
        activityId: displayRow.dataset.activityId,
      };

      editRow
        .querySelector("[data-programme-edit-cancel]")
        ?.addEventListener("click", () => closeEdit());
      editRow.querySelector("[data-programme-edit-first-field]")?.focus();
    }

    Array.from(workspace.querySelectorAll("[data-programme-edit-trigger]")).forEach(
      (trigger) => {
        trigger.addEventListener("click", (event) => {
          event.preventDefault();
          const displayRow = trigger.closest("[data-programme-row]");
          if (displayRow) openEdit(displayRow);
        });
      },
    );

    editForm?.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (!activeEdit) return;

      hideEditError();
      const { activityId, editRow } = activeEdit;
      const saveButton = editRow.querySelector("[data-programme-edit-save]");
      saveButton?.setAttribute("disabled", "disabled");

      try {
        const response = await fetch(
          `/projects/${workspace.dataset.projectId}/programme/activities/${activityId}`,
          {
            method: "PATCH",
            headers: {
              "Content-Type": "application/json",
              Accept: "application/json",
            },
            credentials: "same-origin",
            body: JSON.stringify(collectUpdatePayload(editForm)),
          },
        );

        if (!response.ok) {
          const problem = await response.json().catch(() => null);
          throw new Error(
            parseDetailMessage(problem?.detail) ||
              "Unable to save changes. Check the fields and try again.",
          );
        }

        await refreshWorkspace(workspace, {});
      } catch (error) {
        showEditError(
          error instanceof Error
            ? error.message
            : "Unable to save changes. Check the fields and try again.",
        );
      } finally {
        saveButton?.removeAttribute("disabled");
      }
    });
  }

  async function refreshWorkspace(workspace, { reopenAddForm = false } = {}) {
    let freshWorkspace = null;

    try {
      const response = await fetch(window.location.pathname, {
        headers: { Accept: "text/html" },
        credentials: "same-origin",
      });

      if (response.ok) {
        const html = await response.text();
        const parsed = new DOMParser().parseFromString(html, "text/html");
        freshWorkspace = parsed.querySelector("[data-programme-workspace]");
      }
    } catch (error) {
      freshWorkspace = null;
    }

    if (!freshWorkspace) {
      window.location.reload();
      return;
    }

    workspace.replaceWith(freshWorkspace);
    initWorkspace(freshWorkspace);

    if (reopenAddForm) {
      const trigger = freshWorkspace.querySelector("[data-programme-add-trigger]");
      trigger?.dispatchEvent(new MouseEvent("click", { cancelable: true }));
    }
  }

  document
    .querySelectorAll("[data-programme-workspace]")
    .forEach((workspace) => initWorkspace(workspace));
})();
