/** Tiny non-blocking message at the bottom of the screen. */
const Toast = (() => {
  let timer = null;
  function show(message, ms = 2600) {
    const el = document.getElementById("toast");
    if (!el) return;
    el.textContent = message;
    el.classList.add("show");
    clearTimeout(timer);
    timer = setTimeout(() => el.classList.remove("show"), ms);
  }
  return { show };
})();
