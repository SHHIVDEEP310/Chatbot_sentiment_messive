/**
 * Thin wrapper around fetch(). Session auth is a first-party HTTP-only
 * cookie set by the backend, so every request goes with credentials:
 * "include" and there's no token to manage on the client.
 */
const Api = (() => {
  const BASE = window.APP_CONFIG.API_BASE_URL;

  class ApiError extends Error {
    constructor(message, status, detail) {
      super(message);
      this.status = status;
      this.detail = detail;
    }
  }

  // `body` = JSON object, `form` = FormData (multipart upload).
  async function request(path, { method = "GET", body, form } = {}) {
    let res;
    try {
      res = await fetch(`${BASE}${path}`, {
        method,
        headers: body ? { "Content-Type": "application/json" } : {},
        credentials: "include",
        body: form ? form : body ? JSON.stringify(body) : undefined,
      });
    } catch (networkErr) {
      throw new ApiError(
        "Could not reach the server. Is the backend running?",
        0,
        null
      );
    }

    if (res.status === 204) return null;

    let data = null;
    try {
      data = await res.json();
    } catch {
      /* empty body is fine */
    }

    if (!res.ok) {
      let detail = data && data.detail ? data.detail : res.statusText;
      // FastAPI validation errors arrive as a list of {msg, loc, ...}
      if (Array.isArray(detail)) {
        detail = detail
          .map((d) => (d.msg || "").replace(/^Value error, /, ""))
          .filter(Boolean)
          .join(" ");
      }
      throw new ApiError(
        typeof detail === "string" && detail ? detail : "Request failed",
        res.status,
        detail
      );
    }
    return data;
  }

  const q = encodeURIComponent;

  return {
    ApiError,
    register: (email, password) =>
      request("/api/auth/register", { method: "POST", body: { email, password } }),
    login: (email, password) =>
      request("/api/auth/login", { method: "POST", body: { email, password } }),
    logout: () => request("/api/auth/logout", { method: "POST" }),
    me: () => request("/api/auth/me"),

    predict: (text, chatId) =>
      request("/api/predict", { method: "POST", body: { text, chat_id: chatId } }),
    predictBatch: (texts, chatId) =>
      request("/api/predict/batch", { method: "POST", body: { texts, chat_id: chatId } }),
    predictMedia: (file, chatId) => {
      const form = new FormData();
      form.append("file", file);
      form.append("chat_id", chatId);
      return request("/api/predict/media", { method: "POST", form });
    },

    history: (chatId) =>
      request(`/api/history${chatId ? `?chat_id=${q(chatId)}` : ""}`),
    chats: () => request("/api/chats"),
    shareChat: (chatId) =>
      request(`/api/chats/${q(chatId)}/share`, { method: "POST" }),
    shared: (token) => request(`/api/shared/${q(token)}`),
    deleteMyData: () => request("/api/user/data", { method: "DELETE" }),
  };
})();
