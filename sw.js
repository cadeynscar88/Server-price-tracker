// Minimal service worker: cache app shell, network-first for data.
const SHELL = "pst-shell-v1";
const SHELL_FILES = ["./", "./index.html", "./manifest.webmanifest"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(SHELL).then((c) => c.addAll(SHELL_FILES)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== SHELL).map((k) => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET") return;
  // Data + APIs: network first, fall back to cache
  if (url.pathname.includes("/data/") || url.hostname.includes("api.") || url.hostname.includes("github")) {
    e.respondWith(
      fetch(e.request).then((res) => {
        const copy = res.clone();
        caches.open(SHELL).then((c) => c.put(e.request, copy));
        return res;
      }).catch(() => caches.match(e.request))
    );
    return;
  }
  // Shell: cache first
  e.respondWith(caches.match(e.request).then((hit) => hit || fetch(e.request)));
});
