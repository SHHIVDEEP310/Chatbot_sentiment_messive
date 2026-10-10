/**
 * Minimal, dependency-free pseudo-3D starfield: particles drift toward
 * the viewer along a z-axis, giving depth/parallax without pulling in
 * a 3D library. Deliberately slow and quiet — ambient, not distracting.
 *
 * Starfield.mount(canvas, { count }) can be called for any canvas, so the
 * landing page and the sign-in card share exactly the same background.
 */
const Starfield = (() => {
  const TINTS = ["139,147,255", "95,217,164", "238,240,244"];
  const SPEED = 0.1;
  const prefersReducedMotion = window.matchMedia(
    "(prefers-reduced-motion: reduce)"
  ).matches;

  function mount(canvas, { count = 260 } = {}) {
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    let width = 0, height = 0, cx = 0, cy = 0;
    const stars = [];

    function makeStar() {
      return {
        x: (Math.random() - 0.5) * width,
        y: (Math.random() - 0.5) * height,
        z: Math.random() * width,
        tint: TINTS[Math.floor(Math.random() * TINTS.length)],
      };
    }

    function setup() {
      width = canvas.width = canvas.offsetWidth * devicePixelRatio;
      height = canvas.height = canvas.offsetHeight * devicePixelRatio;
      cx = width / 2;
      cy = height / 2;
      stars.length = 0;
      if (width === 0 || height === 0) return;
      for (let i = 0; i < count; i++) stars.push(makeStar());
    }

    function draw(advance) {
      ctx.clearRect(0, 0, width, height);
      for (const star of stars) {
        if (advance) star.z -= SPEED * width * 0.02;
        if (star.z <= 1) Object.assign(star, makeStar(), { z: width });
        const k = 128 / star.z;
        const sx = star.x * k + cx;
        const sy = star.y * k + cy;
        if (sx < 0 || sx > width || sy < 0 || sy > height) continue;

        const size = Math.max(0.4, (1 - star.z / width) * 2.4) * devicePixelRatio;
        const opacity = Math.min(1, (1 - star.z / width) * 1.4);
        ctx.beginPath();
        ctx.fillStyle = `rgba(${star.tint}, ${opacity * 0.85})`;
        ctx.arc(sx, sy, size, 0, Math.PI * 2);
        ctx.fill();
      }
    }

    function tick() {
      // offsetParent is null while the canvas (or an ancestor) is display:none
      if (canvas.offsetParent !== null) draw(true);
      requestAnimationFrame(tick);
    }

    // Re-measure whenever the canvas changes size (window resize, or a
    // hidden modal being shown for the first time).
    new ResizeObserver(() => {
      setup();
      if (prefersReducedMotion) draw(false);
    }).observe(canvas);

    setup();
    draw(false); // always paint one static frame, even with reduced motion
    if (!prefersReducedMotion) tick();
  }

  return { mount };
})();

Starfield.mount(document.getElementById("starfield"));
Starfield.mount(document.getElementById("auth-stars"), { count: 140 });
