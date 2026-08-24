export function serviceWorkerSource(buildAssets: string[]): string {
  const cacheVersion = buildAssets.map(path => path.split('/').pop()?.replace(/[^a-zA-Z0-9]/g, '')).join('-') || 'dev'
  return `const CACHE = 'xultron-shell-${cacheVersion}'
const BUILD_ASSETS = ${JSON.stringify(buildAssets.map(path => `/${path}`))}
const SHELL = ['/', '/index.html', '/manifest.webmanifest', '/icons/xultron.svg', '/icons/xultron-192.png', '/icons/xultron-512.png', ...BUILD_ASSETS]
self.addEventListener('install', event => event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(SHELL)).then(() => self.skipWaiting())))
self.addEventListener('activate', event => event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(key => key !== CACHE).map(key => caches.delete(key)))).then(() => self.clients.claim())))
self.addEventListener('fetch', event => {
  const request = event.request
  if (request.method !== 'GET' || new URL(request.url).pathname.startsWith('/api/')) return
  if (request.mode === 'navigate') {
    event.respondWith(fetch(request).then(response => { const copy = response.clone(); caches.open(CACHE).then(cache => cache.put('/index.html', copy)); return response }).catch(() => caches.match('/index.html')))
    return
  }
  event.respondWith(caches.match(request).then(cached => cached || fetch(request).then(response => { if (response.ok) { const copy = response.clone(); caches.open(CACHE).then(cache => cache.put(request, copy)) } return response })))
})
`
}
