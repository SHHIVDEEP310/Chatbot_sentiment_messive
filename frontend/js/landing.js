/**
 * Landing page: top-bar links (Research / Future Scope / MinProf /
 * WorkDirectory) and the two small video squares. Everything you are
 * expected to edit lives in js/config.js.
 */
(function initLanding() {
  const cfg = window.APP_CONFIG;

  // ---- top-bar links ----
  document.querySelectorAll(".nav-link").forEach((a) => {
    const url = (cfg.LINKS || {})[a.dataset.link];
    if (url) {
      a.href = url;
      a.target = "_blank";
      a.rel = "noopener noreferrer";
    } else {
      a.addEventListener("click", (e) => {
        e.preventDefault();
        Toast.show(`"${a.textContent}" link is not set yet — add it in js/config.js`);
      });
    }
  });

  // ---- the two squares: play a video if a path is configured ----
  const media = cfg.LANDING_MEDIA || {};
  document.querySelectorAll(".media-slot").forEach((slot) => {
    const video = slot.querySelector("video");
    const src = media[slot.dataset.slot];
    if (!src) {
      video.remove(); // keep the placeholder square
      return;
    }
    video.addEventListener("loadeddata", () => slot.classList.add("has-video"));
    video.addEventListener("error", () => video.remove()); // bad path -> placeholder stays
    video.src = src;
    video.play().catch(() => {});
  });
})();
