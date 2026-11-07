self.addEventListener("push", (e) => {
  let data = {};
  try { data = e.data.json(); } catch (_) { data = { title: "Notification", body: e.data && e.data.text() }; }
  e.waitUntil(self.registration.showNotification(data.title || "ccjournal", {
    body: data.body || "", data: { url: data.url || "/admin/" }, icon: "/static/push/icon.png",
  }));
});
self.addEventListener("notificationclick", (e) => {
  e.notification.close();
  e.waitUntil(clients.openWindow(e.notification.data.url || "/admin/"));
});
