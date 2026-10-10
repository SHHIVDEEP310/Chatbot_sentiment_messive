(function bootstrap() {
  const landing = document.getElementById("landing");
  const dashboard = document.getElementById("dashboard");
  const sidebarOverlay = document.getElementById("sidebar-overlay");

  function showDashboard(user) {
    landing.classList.add("hidden");
    dashboard.classList.remove("hidden");
    // Every visit starts a NEW chat. Older chats stay stored on the server
    // and are reachable from the sidebar ("Recent chats").
    Chat.mount(user);
    Welcome.show();
  }

  function showLanding() {
    dashboard.classList.add("hidden");
    sidebarOverlay.classList.add("hidden");
    Welcome.close();
    landing.classList.remove("hidden");
  }

  Auth.onAuthed(showDashboard);
  Chat.onLoggedOut(showLanding);

  // If a valid session cookie already exists, skip straight to the dashboard.
  Api.me()
    .then(showDashboard)
    .catch(() => showLanding());
})();
