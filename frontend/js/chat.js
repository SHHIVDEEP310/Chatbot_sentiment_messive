const Chat = (() => {
  const $ = (id) => document.getElementById(id);
  const chatLog = $("chat-log");
  const input = $("composer-input");
  const sendBtn = $("composer-send");

  const sidebarOverlay = $("sidebar-overlay");
  const sidebarToggle = $("sidebar-toggle");
  const sidebarClose = $("sidebar-close");
  const sidebarUsername = $("sidebar-username");
  const sidebarAvatar = $("sidebar-avatar");
  const chatList = $("chat-list");
  const newChatBtn = $("new-chat-btn");
  const deleteDataBtn = $("delete-data-btn");
  const logoutBtn = $("logout-btn");

  const shareBtn = $("share-btn");
  const downloadBtn = $("download-btn");

  const attachBtn = $("attach-btn");
  const fileInput = $("file-input");
  const attachment = $("attachment");
  const attachThumb = $("attachment-thumb");
  const attachIcon = $("attachment-icon");
  const attachName = $("attachment-name");
  const attachSize = $("attachment-size");
  const attachRemove = $("attachment-remove");

  const LIMITS = window.APP_CONFIG.MEDIA_LIMITS;

  // ---- state for the chat currently on screen ----
  let chatId = newChatId();
  let entries = []; // result objects of this chat (used for .md export)
  let pendingFile = null;
  let pendingThumbUrl = null;

  function newChatId() {
    if (window.crypto && crypto.randomUUID) return crypto.randomUUID();
    return "c" + Date.now().toString(16) + Math.random().toString(16).slice(2, 10);
  }

  // ------------------------------------------------------------------
  // Chat log helpers
  // ------------------------------------------------------------------
  function scrollToEnd() {
    chatLog.scrollTop = chatLog.scrollHeight;
  }

  function clearEmptyState() {
    const empty = chatLog.querySelector(".chat-empty");
    if (empty) empty.remove();
  }

  function showEmptyStateIfNeeded() {
    if (chatLog.children.length === 0) {
      const p = document.createElement("p");
      p.className = "chat-empty";
      p.textContent =
        "Paste text or emoji and hit send — or tap + to add a photo or short video. Multiple lines are analysed as a batch.";
      chatLog.appendChild(p);
    }
  }

  function addEntry(result) {
    Render.entry(chatLog, result);
    entries.push(result);
    scrollToEnd();
  }

  function showError(err) {
    Render.error(
      chatLog,
      err instanceof Api.ApiError ? err.message : "Something went wrong analysing that input."
    );
    scrollToEnd();
  }

  function resetChat(newId) {
    chatId = newId || newChatId();
    entries = [];
    chatLog.innerHTML = "";
    clearAttachment();
  }

  // ------------------------------------------------------------------
  // Attachment (+) : photo or short video
  // ------------------------------------------------------------------
  const fmtSize = (b) =>
    b >= 1024 * 1024 ? `${(b / (1024 * 1024)).toFixed(1)} MB` : `${Math.max(1, Math.round(b / 1024))} KB`;

  function kindOf(file) {
    if (/^image\/(jpeg|png|webp|gif)$/.test(file.type)) return "image";
    if (/^video\/(mp4|webm|quicktime)$/.test(file.type)) return "video";
    return null;
  }

  function videoDuration(file) {
    return new Promise((resolve) => {
      const url = URL.createObjectURL(file);
      const v = document.createElement("video");
      const done = (val) => {
        URL.revokeObjectURL(url);
        resolve(val);
      };
      v.preload = "metadata";
      v.onloadedmetadata = () => done(isFinite(v.duration) ? v.duration : null);
      v.onerror = () => done(null); // can't preview -> let the server decide
      setTimeout(() => done(null), 4000);
      v.src = url;
    });
  }

  async function pickFile(file) {
    const kind = kindOf(file);
    if (!kind) {
      Toast.show("Only photos (JPG, PNG, WEBP, GIF) and short videos (MP4, WEBM, MOV).");
      return;
    }
    const maxBytes = kind === "image" ? LIMITS.imageBytes : LIMITS.videoBytes;
    if (file.size > maxBytes) {
      Toast.show(`That ${kind} is too large — max ${Math.round(maxBytes / (1024 * 1024))} MB.`);
      return;
    }
    if (kind === "video") {
      const d = await videoDuration(file);
      if (d !== null && d > LIMITS.videoSeconds) {
        Toast.show(`Video is too long — max ${LIMITS.videoSeconds} seconds.`);
        return;
      }
    }
    clearAttachment();
    pendingFile = file;
    attachName.textContent = file.name;
    attachSize.textContent = `${kind} · ${fmtSize(file.size)}`;
    if (kind === "image") {
      pendingThumbUrl = URL.createObjectURL(file);
      attachThumb.src = pendingThumbUrl;
      attachThumb.classList.remove("hidden");
      attachIcon.classList.add("hidden");
    } else {
      attachThumb.classList.add("hidden");
      attachIcon.classList.remove("hidden");
    }
    attachment.classList.remove("hidden");
    input.focus();
  }

  function clearAttachment() {
    pendingFile = null;
    if (pendingThumbUrl) URL.revokeObjectURL(pendingThumbUrl);
    pendingThumbUrl = null;
    attachThumb.removeAttribute("src");
    attachment.classList.add("hidden");
    fileInput.value = "";
  }

  attachBtn.addEventListener("click", () => fileInput.click());
  fileInput.addEventListener("change", () => {
    if (fileInput.files && fileInput.files[0]) pickFile(fileInput.files[0]);
  });
  attachRemove.addEventListener("click", clearAttachment);

  // ------------------------------------------------------------------
  // Sending
  // ------------------------------------------------------------------
  async function sendText(lines) {
    try {
      if (lines.length === 1) {
        addEntry(await Api.predict(lines[0], chatId));
      } else {
        Render.batchLabel(chatLog, lines.length);
        const { results } = await Api.predictBatch(lines, chatId);
        results.forEach((r) => {
          try {
            addEntry(r);
          } catch (err) {
            console.error("Failed to render one batch result:", err);
            Render.error(chatLog, `Couldn't display a result for: "${r.input_text}"`);
          }
        });
      }
    } catch (err) {
      showError(err);
    }
  }

  async function sendMedia(file) {
    const kind = kindOf(file) || "file";
    const pending = document.createElement("div");
    pending.className = "entry entry-pending";
    pending.textContent = `Extracting text from your ${kind}…`;
    chatLog.appendChild(pending);
    scrollToEnd();
    try {
      const result = await Api.predictMedia(file, chatId);
      pending.remove();
      addEntry(result);
    } catch (err) {
      pending.remove();
      showError(err);
    }
  }

  async function submitCurrentInput() {
    const lines = input.value
      .split("\n")
      .map((l) => l.trim())
      .filter((l) => l.length > 0);
    const file = pendingFile;
    if (lines.length === 0 && !file) return;
    if (sendBtn.disabled) return;

    clearEmptyState();
    input.value = "";
    autoResize();
    sendBtn.disabled = true;
    if (file) clearAttachment();

    try {
      if (lines.length) await sendText(lines);
      if (file) await sendMedia(file);
    } finally {
      sendBtn.disabled = false;
      input.focus();
    }
  }

  function autoResize() {
    input.style.height = "auto";
    input.style.height = Math.min(input.scrollHeight, 140) + "px";
  }

  input.addEventListener("input", autoResize);
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submitCurrentInput();
    }
  });
  sendBtn.addEventListener("click", submitCurrentInput);

  // ------------------------------------------------------------------
  // Download (.md) and Share (link)
  // ------------------------------------------------------------------
  const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1);
  const pad = (n) => String(n).padStart(2, "0");

  function toMarkdown() {
    const out = ["# Sentiment chat", "", `_Exported ${new Date().toLocaleString()}_`, ""];
    entries.forEach((r, i) => {
      out.push(`## ${i + 1}. ${cap(r.predicted_label)}`, "");
      if (r.source_type === "image" || r.source_type === "video") {
        out.push(
          `**Source:** ${r.source_type} — ${r.source_name || "upload"} (text extracted from the ${r.source_type})`,
          ""
        );
      }
      out.push(...r.input_text.split("\n").map((l) => (l ? `> ${l}` : ">")), "");
      out.push(
        "**Scores:** " +
          Object.entries(r.scores)
            .map(([k, v]) => `${k} ${(v * 100).toFixed(1)}%`)
            .join(" · "),
        ""
      );
      if (r.insight) out.push(`**Insight:** ${r.insight}`, "");
    });
    return out.join("\n");
  }

  downloadBtn.addEventListener("click", () => {
    if (entries.length === 0) {
      Toast.show("Nothing to download yet — send a message first.");
      return;
    }
    const d = new Date();
    const name = `sentiment-chat-${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}-${pad(d.getHours())}${pad(d.getMinutes())}.md`;
    const url = URL.createObjectURL(new Blob([toMarkdown()], { type: "text/markdown;charset=utf-8" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = name;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  });

  shareBtn.addEventListener("click", async () => {
    if (entries.length === 0) {
      Toast.show("Nothing to share yet — send a message first.");
      return;
    }
    let url;
    try {
      const { token } = await Api.shareChat(chatId);
      url = new URL(`shared.html?t=${encodeURIComponent(token)}`, location.href).href;
    } catch (err) {
      Toast.show(err.message || "Could not create a share link.");
      return;
    }
    if (navigator.share) {
      try {
        await navigator.share({ title: "Sentiment chat", url });
        return;
      } catch (err) {
        if (err && err.name === "AbortError") return; // user closed the share sheet
      }
    }
    try {
      await navigator.clipboard.writeText(url);
      Toast.show("Share link copied — anyone with it can view this chat.", 3600);
    } catch {
      window.prompt("Copy this share link:", url);
    }
  });

  // ------------------------------------------------------------------
  // Sidebar: new chat, recent chats, MCP link, delete, log out
  // ------------------------------------------------------------------
  async function loadChatList() {
    chatList.innerHTML = "";
    const note = (text) => {
      const p = document.createElement("p");
      p.className = "sidebar-note";
      p.textContent = text;
      chatList.appendChild(p);
    };
    try {
      const { items } = await Api.chats();
      if (items.length === 0) return note("No saved chats yet.");
      items.forEach((c) => {
        const b = document.createElement("button");
        b.className = "chat-item" + (c.chat_id === chatId ? " active" : "");
        b.textContent = c.title;
        b.title = c.title;
        b.addEventListener("click", () => openChat(c.chat_id));
        chatList.appendChild(b);
      });
    } catch {
      note("Couldn't load chats.");
    }
  }

  async function openChat(id) {
    try {
      const { items } = await Api.history(id);
      resetChat(id);
      Render.items(chatLog, items);
      entries = items.slice();
      closeSidebar();
      scrollToEnd();
    } catch (err) {
      Toast.show(err.message || "Could not open that chat.");
    }
  }

  function startNewChat() {
    resetChat();
    showEmptyStateIfNeeded();
    closeSidebar();
    input.focus();
  }

  function openSidebar() {
    sidebarOverlay.classList.remove("hidden");
    loadChatList();
  }
  function closeSidebar() {
    sidebarOverlay.classList.add("hidden");
  }
  sidebarToggle.addEventListener("click", openSidebar);
  sidebarClose.addEventListener("click", closeSidebar);
  sidebarOverlay.addEventListener("click", (e) => {
    if (e.target === sidebarOverlay) closeSidebar();
  });
  newChatBtn.addEventListener("click", startNewChat);

  deleteDataBtn.addEventListener("click", async () => {
    const confirmed = window.confirm(
      "Delete all of your submission history and share links? This can't be undone."
    );
    if (!confirmed) return;
    try {
      await Api.deleteMyData();
      startNewChat();
    } catch (err) {
      window.alert(err.message || "Could not delete your data.");
    }
  });

  let onLoggedOut = () => {};
  logoutBtn.addEventListener("click", async () => {
    try {
      await Api.logout();
    } catch {
      /* proceed regardless — client-side state is what matters here */
    }
    closeSidebar();
    resetChat();
    onLoggedOut();
  });

  // Called on every login / page load: always a fresh, empty chat.
  function mount(user) {
    sidebarUsername.textContent = user.email;
    sidebarAvatar.textContent = user.email.slice(0, 1);
    resetChat();
    showEmptyStateIfNeeded();
  }

  return {
    mount,
    focus: () => input.focus(),
    onLoggedOut: (fn) => {
      onLoggedOut = fn;
    },
  };
})();
