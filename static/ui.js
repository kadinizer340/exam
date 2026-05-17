document.addEventListener("DOMContentLoaded", () => {
  const loadingOverlay = document.querySelector("[data-loading-overlay]");
  const loadingMessage = document.querySelector("[data-loading-message]");
  const loadingActions = document.querySelector("[data-loading-actions]");
  const loadingDismiss = document.querySelector("[data-loading-dismiss]");
  const defaultLoadingMessage = loadingMessage ? loadingMessage.textContent : "";
  let loadingFallbackTimer = null;

  const hideLoadingOverlay = () => {
    if (!loadingOverlay) {
      return;
    }

    loadingOverlay.hidden = true;

    if (loadingFallbackTimer) {
      window.clearTimeout(loadingFallbackTimer);
      loadingFallbackTimer = null;
    }

    if (loadingMessage) {
      loadingMessage.textContent = defaultLoadingMessage;
    }

    if (loadingActions) {
      loadingActions.hidden = true;
    }
  };

  const showLoadingOverlay = () => {
    if (!loadingOverlay) {
      return;
    }

    loadingOverlay.hidden = false;

    if (loadingMessage) {
      loadingMessage.textContent = defaultLoadingMessage;
    }

    if (loadingActions) {
      loadingActions.hidden = true;
    }

    if (loadingFallbackTimer) {
      window.clearTimeout(loadingFallbackTimer);
    }

    loadingFallbackTimer = window.setTimeout(() => {
      if (loadingMessage) {
        loadingMessage.textContent =
          "This is taking longer than usual. The seating plan may already be ready, so you can keep working or open the seating view.";
      }

      if (loadingActions) {
        loadingActions.hidden = false;
      }
    }, 12000);
  };

  window.addEventListener("pageshow", hideLoadingOverlay);

  if (loadingDismiss) {
    loadingDismiss.addEventListener("click", hideLoadingOverlay);
  }

  document.querySelectorAll("[data-loading-trigger]").forEach((trigger) => {
    trigger.addEventListener("click", (event) => {
      if (event.defaultPrevented) {
        return;
      }

      if (trigger.tagName === "A") {
        const href = trigger.getAttribute("href");
        const opensElsewhere =
          trigger.target && trigger.target.toLowerCase() !== "_self";
        const modifiedClick =
          event.button !== 0 ||
          event.metaKey ||
          event.ctrlKey ||
          event.shiftKey ||
          event.altKey;

        if (!href || href.startsWith("#") || opensElsewhere || modifiedClick) {
          return;
        }
      }

      showLoadingOverlay();
    });
  });

  document.querySelectorAll("[data-file-input]").forEach((input) => {
    const dropzone = input.closest("[data-dropzone]");
    const fileName = dropzone
      ? dropzone.querySelector("[data-file-name]")
      : null;

    const refreshFileState = () => {
      const selectedFile = input.files && input.files.length ? input.files[0] : null;

      if (fileName) {
        fileName.textContent = selectedFile
          ? selectedFile.name
          : "No file selected yet";
      }

      if (dropzone) {
        dropzone.classList.toggle("has-file", Boolean(selectedFile));
      }
    };

    input.addEventListener("change", refreshFileState);
    refreshFileState();
  });

  const classForm = document.querySelector("[data-class-form]");
  if (classForm) {
    const counter = document.querySelector("[data-selected-count]");
    const inputs = classForm.querySelectorAll("input[type='checkbox']");

    const updateSelectionCount = () => {
      const total = Array.from(inputs).filter((input) => input.checked).length;
      if (counter) {
        counter.textContent = String(total);
      }
    };

    inputs.forEach((input) => {
      input.addEventListener("change", updateSelectionCount);
    });

    updateSelectionCount();
  }
});
