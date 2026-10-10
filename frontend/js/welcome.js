/**
 * Small welcome alert dialog shown each time the dashboard opens.
 * One question, four radio options (only one can be selected at a time).
 * Fully skippable — close button, Skip, Esc or a click outside all just
 * dismiss it, so nothing is blocked.
 */
const Welcome = (() => {
  const overlay = document.getElementById("welcome-overlay");
  const dialog = overlay.querySelector(".alert-dialog");
  const radios = overlay.querySelectorAll('input[name="welcome-q"]');
  const continueBtn = document.getElementById("wd-continue");

  dialog.tabIndex = -1;

  function isOpen() {
    return !overlay.classList.contains("hidden");
  }

  function show() {
    radios.forEach((r) => (r.checked = false));
    continueBtn.disabled = true;
    overlay.classList.remove("hidden");
    dialog.focus();
  }

  function close() {
    overlay.classList.add("hidden");
    Chat.focus();
  }

  radios.forEach((r) =>
    r.addEventListener("change", () => {
      continueBtn.disabled = false;
    })
  );
  continueBtn.addEventListener("click", close);
  document.getElementById("wd-skip").addEventListener("click", close);
  document.getElementById("wd-close").addEventListener("click", close);
  overlay.addEventListener("click", (e) => {
    if (e.target === overlay) close();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && isOpen()) close();
  });

  return { show, close };
})();
