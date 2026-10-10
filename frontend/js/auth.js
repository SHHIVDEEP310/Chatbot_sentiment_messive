const Auth = (() => {
  const overlay = document.getElementById("auth-overlay");
  const closeBtn = document.getElementById("auth-close");
  const tabs = document.querySelectorAll(".auth-tab");
  const loginForm = document.getElementById("login-form");
  const registerForm = document.getElementById("register-form");
  const loginError = document.getElementById("login-error");
  const registerError = document.getElementById("register-error");

  let onAuthed = () => {};

  // ------------------------------------------------------------------
  // Email check (format only — mirrors the backend rule)
  // ------------------------------------------------------------------
  const EMAIL_RE =
    /^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$/;
  const isValidEmail = (v) => v.trim().length <= 254 && EMAIL_RE.test(v.trim());

  function bindEmailField(input, statusEl) {
    function paint(state) {
      input.classList.toggle("is-valid", state === "ok");
      input.classList.toggle("is-invalid", state === "bad");
      statusEl.className = "field-status" + (state ? ` ${state}` : "");
      statusEl.textContent =
        state === "ok"
          ? "✓ Valid email"
          : state === "bad"
          ? "✗ Not a valid email — use the form name@example.com"
          : "";
    }
    function check({ strict }) {
      const v = input.value;
      if (!v.trim()) return paint("");
      if (isValidEmail(v)) return paint("ok");
      // While typing, only complain once there's an "@" (or on blur).
      paint(strict || v.includes("@") ? "bad" : "");
    }
    input.addEventListener("input", () => check({ strict: false }));
    input.addEventListener("blur", () => check({ strict: true }));
    return {
      validate() {
        const ok = isValidEmail(input.value);
        paint(ok ? "ok" : "bad");
        if (!ok) input.focus();
        return ok;
      },
      reset: () => paint(""),
    };
  }

  const loginEmail = bindEmailField(
    document.getElementById("login-email"),
    document.getElementById("login-email-status")
  );
  const registerEmail = bindEmailField(
    document.getElementById("register-email"),
    document.getElementById("register-email-status")
  );

  // ------------------------------------------------------------------
  // Password: the user types their own OR takes a suggested one
  // ------------------------------------------------------------------
  const pwOwn = document.getElementById("pw-own");
  const pwSuggest = document.getElementById("pw-suggest");
  const ownInput = document.getElementById("register-password");
  const suggestedInput = document.getElementById("suggested-password");
  const modeBtns = document.querySelectorAll(".pw-mode");
  let pwMode = "own";

  // Unbiased random int via rejection sampling (crypto, not Math.random).
  function randInt(max) {
    const buf = new Uint32Array(1);
    const limit = Math.floor(0x100000000 / max) * max;
    let x;
    do {
      crypto.getRandomValues(buf);
      x = buf[0];
    } while (x >= limit);
    return x % max;
  }

  function suggestPassword(length = 14) {
    // ambiguous characters (0 O 1 l I) left out so it's easy to read/type
    const sets = [
      "abcdefghijkmnopqrstuvwxyz",
      "ABCDEFGHJKLMNPQRSTUVWXYZ",
      "23456789",
      "!@#$%^&*-_=+?",
    ];
    const all = sets.join("");
    const chars = sets.map((s) => s[randInt(s.length)]); // one of each kind
    while (chars.length < length) chars.push(all[randInt(all.length)]);
    for (let i = chars.length - 1; i > 0; i--) {
      const j = randInt(i + 1);
      [chars[i], chars[j]] = [chars[j], chars[i]];
    }
    return chars.join("");
  }

  function setPwMode(mode) {
    pwMode = mode;
    modeBtns.forEach((b) => {
      const on = b.dataset.pwMode === mode;
      b.classList.toggle("active", on);
      b.setAttribute("aria-selected", String(on));
    });
    pwOwn.classList.toggle("hidden", mode !== "own");
    pwSuggest.classList.toggle("hidden", mode !== "suggest");
    if (mode === "suggest" && !suggestedInput.value) {
      suggestedInput.value = suggestPassword();
    }
  }
  modeBtns.forEach((b) => b.addEventListener("click", () => setPwMode(b.dataset.pwMode)));

  document.getElementById("pw-regen").addEventListener("click", () => {
    suggestedInput.value = suggestPassword();
  });
  document.getElementById("pw-copy").addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(suggestedInput.value);
    } catch {
      suggestedInput.select();
      document.execCommand("copy");
    }
    Toast.show("Password copied");
  });

  // ------------------------------------------------------------------
  // Modal open/close + submit
  // ------------------------------------------------------------------
  function resetRegister() {
    registerForm.reset();
    suggestedInput.value = "";
    setPwMode("own");
    registerEmail.reset();
  }

  function open(tab = "login") {
    overlay.classList.remove("hidden");
    setTab(tab);
    loginError.textContent = "";
    registerError.textContent = "";
  }

  function close() {
    overlay.classList.add("hidden");
  }

  function setTab(tab) {
    tabs.forEach((t) => t.classList.toggle("active", t.dataset.tab === tab));
    loginForm.classList.toggle("hidden", tab !== "login");
    registerForm.classList.toggle("hidden", tab !== "register");
  }

  tabs.forEach((t) => t.addEventListener("click", () => setTab(t.dataset.tab)));
  closeBtn.addEventListener("click", close);
  overlay.addEventListener("click", (e) => {
    if (e.target === overlay) close();
  });

  loginForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    loginError.textContent = "";
    if (!loginEmail.validate()) return;
    const fd = new FormData(loginForm);
    try {
      const user = await Api.login(fd.get("email").trim(), fd.get("password"));
      close();
      loginForm.reset();
      loginEmail.reset();
      onAuthed(user);
    } catch (err) {
      loginError.textContent = err.message || "Sign in failed.";
    }
  });

  registerForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    registerError.textContent = "";
    if (!registerEmail.validate()) return;

    const password = pwMode === "suggest" ? suggestedInput.value : ownInput.value;
    if (password.length < 8) {
      registerError.textContent = "Password must be at least 8 characters.";
      return;
    }
    const email = new FormData(registerForm).get("email").trim();
    try {
      const user = await Api.register(email, password);
      close();
      resetRegister();
      onAuthed(user);
    } catch (err) {
      registerError.textContent = err.message || "Registration failed.";
    }
  });

  document.querySelectorAll("[data-open-auth]").forEach((btn) => {
    btn.addEventListener("click", () => open(btn.dataset.openAuth));
  });

  return {
    open,
    close,
    onAuthed: (fn) => {
      onAuthed = fn;
    },
  };
})();
