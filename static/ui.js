document.addEventListener("DOMContentLoaded", () => {
  const loadingOverlay = document.querySelector("[data-loading-overlay]");

  document.querySelectorAll("[data-loading-trigger]").forEach((trigger) => {
    trigger.addEventListener("click", () => {
      if (loadingOverlay) {
        loadingOverlay.hidden = false;
      }
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
