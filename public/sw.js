/* DYNAMIC offline cache: stale-while-revalidate for same-origin GET requests */
const CACHE = 'dynamic-v1';
const SHELL = ['./', 'index.html', 'reader/index.html', 'reader/app.js', 'reader/app.css', 'assets/dynamic-icon.svg', 'assets/dynamic-logo.svg', 'manifest.webmanifest'];
self.addEventListener('install', (e) => { e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting())); });
self.addEventListener('activate', (e) => {
  e.waitUntil(caches.keys().then((ks) => Promise.all(ks.filter((k) => k !== CACHE).map((k) => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener('fetch', (e) => {
  const req = e.request;
  if (req.method !== 'GET' || new URL(req.url).origin !== location.origin) return;
  e.respondWith(caches.open(CACHE).then(async (c) => {
    const hit = await c.match(req, { ignoreSearch: req.mode === 'navigate' });
    const net = fetch(req).then((r) => { if (r.ok && !req.url.endsWith('.pdf')) c.put(req, r.clone()); return r; }).catch(() => hit);
    return hit || net;
  }));
});
