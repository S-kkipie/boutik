// Caches the app shell so the till opens instantly on 2G and even offline.
// API calls always go to the network: money state is never served from cache.
const VERSION = "boutik-v1";
const SHELL = [
  "/",
  "/static/app.css",
  "/static/app.js",
  "/static/ui.js",
  "/static/pay.js",
  "/static/pay.html",
  "/static/icons/icon.svg",
  "/manifest.webmanifest",
];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(VERSION).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== VERSION).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.origin !== location.origin || url.pathname.startsWith("/api/")) return;
  // Network first (so a deploy is picked up at once), cache after 4 s or when offline.
  // Pay links fall back to the cached pay page.
  const key = url.pathname.startsWith("/p/") ? "/static/pay.html" : url.pathname;
  e.respondWith(
    caches.open(VERSION).then(async (cache) => {
      const network = fetch(e.request).then((r) => {
        if (r.ok && SHELL.includes(url.pathname)) cache.put(url.pathname, r.clone());
        return r;
      });
      const timeout = new Promise((resolve) => setTimeout(resolve, 4000));
      try {
        const r = await Promise.race([network, timeout]);
        if (r) return r;
      } catch { /* offline */ }
      return (await cache.match(key)) || network;
    }),
  );
});
