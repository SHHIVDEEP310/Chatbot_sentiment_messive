// Local dev: frontend on :5500 talks to FastAPI on :8000.
// Anywhere else (e.g. Vercel): use same-origin /api, which vercel.json
// rewrites to the backend. Same-origin keeps the HTTP-only session cookie
// first-party, so no cross-site cookie/CORS setup is needed.
const isLocal = ["localhost", "127.0.0.1"].includes(location.hostname);
window.APP_CONFIG = {
  API_BASE_URL: isLocal ? `http://${location.hostname}:8000` : "",

  // ---- Landing-page links (top bar, next to Sign In / Sign Up) ----
  // Research  -> opens this document (replace with your paper, e.g. "docs/paper.pdf")
  // FutureScope -> project information page
  // MinProf   -> your portfolio link
  // WorkDirectory -> set the URL you want; empty = shows a "link not set" message
  LINKS: {
    research: "docs/research-paper.html",
    futureScope: "future-scope.html",
    minProf: "https://portfolio-shivdeep.netlify.app",
    workDirectory: "https://hvd8hd-oceq7xtkk-arcadawebapps3.vercel.app/",
  },

  // ---- The two small squares under the 3D background on the landing page ----
  // Put your video files in frontend/media/ and set the paths here,
  // e.g. left: "media/demo-1.mp4". Empty = placeholder square.
  LANDING_MEDIA: {
    left: "media/demo-1.mp4",
    right: "media/demo-2.mp4",
  },

  // ---- Upload limits for the "+" button (must match backend/.env) ----
  MEDIA_LIMITS: {
    imageBytes: 5 * 1024 * 1024,
    videoBytes: 20 * 1024 * 1024,
    videoSeconds: 30,
  },
};
