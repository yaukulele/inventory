// 庫存系統 Service Worker — 加快「登入＋使用」速度
// 策略：
//  - App shell（index.html）：stale-while-revalidate → 開頁秒出快取版，背景再更新，下次開就是新版
//  - 不可變 CDN（Firebase SDK gstatic、Google Fonts）：cache-first，第二次起完全免下載
//  - 商品圖（catbox 等）：cache-first，捲動/重畫時免重抓
//  - Firebase 即時資料庫 / 匿名登入流量：完全略過，交給 SDK，確保即時同步不受影響
// 改版時把 VER 加一號，舊快取會自動清掉。
const VER = "inv-v12";
const SHELL = VER + "-shell";
const CDN = VER + "-cdn";
const IMG = VER + "-img";

self.addEventListener("install", () => {
  self.skipWaiting();
});

self.addEventListener("activate", (e) => {
  e.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.filter(k => !k.startsWith(VER)).map(k => caches.delete(k)));
    await self.clients.claim();
  })());
});

const CDN_HOSTS = ["www.gstatic.com", "fonts.googleapis.com", "fonts.gstatic.com"];
// Anything Firebase-realtime/auth related must pass straight through to the network.
const BYPASS = /firebaseio\.com|firebasedatabase\.app|identitytoolkit|securetoken|firebaseinstallations|firebaseremoteconfig|google-analytics|googletagmanager/;

async function staleWhileRevalidate(req, cacheName) {
  const cache = await caches.open(cacheName);
  const cached = await cache.match(req, { ignoreSearch: true });
  const net = fetch(req).then(r => {
    if (r && (r.ok || r.type === "opaque")) cache.put(req, r.clone());
    return r;
  }).catch(() => null);
  return cached || (await net) || fetch(req);
}

async function cacheFirst(req, cacheName) {
  const cache = await caches.open(cacheName);
  const cached = await cache.match(req);
  if (cached) return cached;
  const r = await fetch(req).catch(() => null);
  if (r && (r.ok || r.type === "opaque")) cache.put(req, r.clone());
  return r || fetch(req);
}

self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;
  let url;
  try { url = new URL(req.url); } catch (_) { return; }
  if (BYPASS.test(url.href)) return; // let Firebase SDK handle its own traffic

  // App shell — the HTML document
  if (req.mode === "navigate" ||
      (url.origin === location.origin && (url.pathname.endsWith("/") || url.pathname.endsWith("index.html")))) {
    e.respondWith(staleWhileRevalidate(req, SHELL));
    return;
  }
  // Immutable CDN assets (Firebase SDK, Google Fonts)
  if (CDN_HOSTS.includes(url.hostname)) {
    e.respondWith(cacheFirst(req, CDN));
    return;
  }
  // Product images (catbox / yamusic / imgur / lh3 …)
  if (req.destination === "image") {
    e.respondWith(cacheFirst(req, IMG));
    return;
  }
  // everything else: default network
});
