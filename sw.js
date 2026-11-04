// 摨怠?蝟餌絞 Service Worker ???翰??伐?雿輻?漲
// 蝑嚗?//  - App shell嚗ndex.html嚗?stale-while-revalidate ????蝘敹怠??????堆?銝活?停?舀??//  - 銝霈?CDN嚗irebase SDK gstatic?oogle Fonts嚗?cache-first嚗洵鈭活韏瑕??典?銝?
//  - ????catbox 蝑?嚗ache-first嚗???????
//  - Firebase ?單?鞈?摨?/ ?踹??餃瘚?嚗??函??鈭斤策 SDK嚗Ⅱ靽??甇乩??蔣??// ?寧??? VER ?????翰???芸?皜???const VER = "inv-v48";
const IMG_MAX = 500; // ???翰????LRU嚗??踹??瑟??刻?蝵桐??⊿??瑕之嚗里??2026-10-10 C3嚗?const SHELL = VER + "-shell";
// 2026-10-23嚗DN 頝???敹怠??迂銝??韏????瘥活?寧?嚗ER+1嚗停??????
// 摨瘥活?湔敺洵銝甈⊿??質??嗾?曉撐???irebase SDK ?銝?銝?DN 蝬脣??祈澈撣嗥??祈????? IMG_MAX 銝?嚗??閬?????const CDN = "inv-cdn-keep";
const IMG = "inv-img-keep";

self.addEventListener("install", () => {
  self.skipWaiting();
});

self.addEventListener("activate", (e) => {
  e.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.filter(k => !k.startsWith(VER) && k !== CDN && k !== IMG).map(k => caches.delete(k)));
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

// ???剁?cache-first 嚗?銝? LRU嚗ache API ??keys() 靘??仿?摨??芸??ｇ??芣???
async function cacheFirstImg(req) {
  const cache = await caches.open(IMG);
  const cached = await cache.match(req);
  if (cached) return cached;
  const r = await fetch(req).catch(() => null);
  if (r && (r.ok || r.type === "opaque")) {
    await cache.put(req, r.clone());
    trimCache(cache, IMG_MAX);
  }
  return r || fetch(req);
}

async function trimCache(cache, max) {
  try {
    const keys = await cache.keys();
    const over = keys.length - max;
    for (let i = 0; i < over; i++) await cache.delete(keys[i]);
  } catch (_) { /* best effort */ }
}

self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;
  let url;
  try { url = new URL(req.url); } catch (_) { return; }
  if (BYPASS.test(url.href)) return; // let Firebase SDK handle its own traffic

  // App shell ??the HTML document
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
  // Product images (catbox / yamusic / imgur / lh3 ?? ?????? LRU 敹怠?
  if (req.destination === "image") {
    e.respondWith(cacheFirstImg(req));
    return;
  }
  // everything else: default network
});
