/* DYNAMIC offline cache: stale-while-revalidate for same-origin GET requests */
const CACHE = 'dynamic-v9';
// Full-score page images are cached only after a viewer has opened them, in their own bounded cache.
const SCORE_CACHE = 'dynamic-score-v1';
const SCORE_MAX = 120;
const SHELL = ['./', 'app.js', 'app.css', 'catalog.json', 'reader/', 'reader/app.js', 'reader/app.css', 'reader/parts.json', 'reader/horn-fingerings.json', 'reader/memo.js', 'reader/memo-model.mjs', 'reader/memo.css', 'assets/dynamic-icon.svg', 'assets/dynamic-logo.svg', 'assets/instrument-horn.png', 'assets/instrument-trombone.png', 'manifest.webmanifest'];
self.addEventListener('install', (e) => { e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting())); });
self.addEventListener('activate', (e) => {
  e.waitUntil(caches.keys().then((ks) => Promise.all(ks.filter((k) => k !== CACHE && k !== SCORE_CACHE).map((k) => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener('fetch', (e) => {
  const req = e.request;
  if (req.method !== 'GET' || new URL(req.url).origin !== location.origin) return;
  const requestUrl = new URL(req.url);
  // Login and per-user memo API responses must never be cached or served offline.
  if (/^\/(?:api\/|login$|logout$)/.test(requestUrl.pathname)) return;
  // Cloudflare redirects explicit index.html URLs to their directory URLs.
  // Safari rejects redirected responses returned from a service worker, so
  // request the canonical directory route directly and preserve query params.
  if (req.mode === 'navigate' && requestUrl.pathname.endsWith('/index.html')) {
    requestUrl.pathname = requestUrl.pathname.slice(0, -'index.html'.length) || '/';
  }
  if (/\/score\/.+\.webp$/.test(requestUrl.pathname)) {           // cache-first, trimmed oldest-first
    e.respondWith(caches.open(SCORE_CACHE).then(async (c) => {
      const hit = await c.match(req); if (hit) return hit;
      const r = await fetch(req);
      if (r.ok) {
        await c.put(req, r.clone());
        const keys = await c.keys();
        await Promise.all(keys.slice(0, Math.max(0, keys.length - SCORE_MAX)).map((k) => c.delete(k)));
      }
      return r;
    }));
    return;
  }
  const cacheKey = requestUrl.href === req.url ? req : requestUrl.href;
  const networkRequest = requestUrl.href === req.url
    ? req
    : new Request(requestUrl.href, { credentials: req.credentials, headers: req.headers });
  e.respondWith(caches.open(CACHE).then(async (c) => {
    const hit = await c.match(cacheKey, { ignoreSearch: req.mode === 'navigate' });
    const net = fetch(networkRequest).then((r) => { if (r.ok && !requestUrl.pathname.endsWith('.pdf')) c.put(cacheKey, r.clone()); return r; }).catch(() => hit);
    return hit || net;
  }));
});
