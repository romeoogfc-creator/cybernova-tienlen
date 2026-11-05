// Minimal service worker: it only makes the game installable ("Add to Home screen").
// It never caches anything, so players always get the newest version of the game.
self.addEventListener('install', function () { self.skipWaiting(); });
self.addEventListener('activate', function (e) { e.waitUntil(self.clients.claim()); });
self.addEventListener('fetch', function () { /* network only */ });