// sw.js — offline support: the app shell is cached; data and notes are network-first with the
// last good copy as the fallback, so recent meetings still open with no signal.
const SHELL = 'shell-v1';
const DATA = 'data-v1';
const FILES = ['/', '/index.html', '/app.css', '/app.js', '/md.js', '/manifest.webmanifest', '/icon-180.png'];
self.addEventListener('install', e => { e.waitUntil(caches.open(SHELL).then(c => c.addAll(FILES)).then(() => self.skipWaiting())); });
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== SHELL && k !== DATA).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener('fetch', e => {
  const u = new URL(e.request.url);
  if (e.request.method !== 'GET' || u.origin !== location.origin) return;
  if (u.pathname.startsWith('/api/audio/')) return;   // media: always live
  if (u.pathname === '/api/data' || u.pathname.startsWith('/api/meeting/')) {
    e.respondWith(fetch(e.request).then(r => { if (r.ok) { const c = r.clone(); caches.open(DATA).then(x => x.put(e.request, c)); } return r; })
      .catch(() => caches.match(e.request).then(r => r || Response.error())));
    return;
  }
  if (u.pathname.startsWith('/api/')) return;
  // shell: network first so updates land right away, cache when offline
  e.respondWith(fetch(e.request).then(r => { if (r.ok && FILES.includes(u.pathname)) { const c = r.clone(); caches.open(SHELL).then(x => x.put(e.request, c)); } return r; })
    .catch(() => caches.match(e.request).then(r => r || caches.match('/index.html'))));
});
