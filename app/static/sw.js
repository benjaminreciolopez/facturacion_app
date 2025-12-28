const CACHE_VERSION = "v4";
const STATIC_CACHE = `static-${CACHE_VERSION}`;
const DYNAMIC_CACHE = `dynamic-${CACHE_VERSION}`;

const STATIC_ASSETS = [
  "/",
  "/dashboard",
  "/facturas",
  "/facturas/offline",
  "/offline",

  "/static/manifest.json",
  "/static/style.css",
  "/static/js/offline_db.js",
  "/static/js/offline_sync.js",
  "/static/pwa/icon-192.png",
  "/static/pwa/icon-512.png",
];

/* ==========================
   INSTALL
========================== */
self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(STATIC_CACHE).then((cache) => cache.addAll(STATIC_ASSETS))
  );
  self.skipWaiting();
});

/* ==========================
   ACTIVATE
========================== */
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys
            .filter((k) => k !== STATIC_CACHE && k !== DYNAMIC_CACHE)
            .map((k) => caches.delete(k))
        )
      )
  );
  self.clients.claim();
});

/* ==========================
   IndexedDB SUPPORT
========================== */
importScripts("/static/js/offline_db.js");

/* ==========================
   BACKGROUND SYNC
========================== */
self.addEventListener("sync", (event) => {
  if (event.tag === "sync-facturas-offline") {
    event.waitUntil(syncOfflineFacturasSW());
  }
});

async function syncOfflineFacturasSW() {
  try {
    const pendientes = await OfflineDB.getFacturasPendientes();
    if (!pendientes.length) return;

    for (const item of pendientes) {
      try {
        const res = await fetch("/api/offline/facturas", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            offline_id: item.temp_id,
            ...item.data,
          }),
        });

        const data = await res.json().catch(() => ({}));

        if (!res.ok || !data.ok) {
          await OfflineDB.marcarConError(
            item.temp_id,
            data.error || data.detail || "Error al sincronizar"
          );
          continue;
        }

        // 🔥 Marca sincronizada
        await OfflineDB.marcarComoSincronizada(item.temp_id);

        // 🔥 Notificación del SW
        if (self.registration?.showNotification) {
          await self.registration.showNotification("Factura sincronizada", {
            body: "Un borrador offline ha sido sincronizado correctamente.",
            icon: "/static/pwa/icon-192.png",
            badge: "/static/pwa/icon-192.png",
          });
        }

        // 🔥 Avisar a todas las pestañas para refrescar UI
        const clientsList = await self.clients.matchAll({
          includeUncontrolled: true,
        });

        clientsList.forEach((client) => {
          client.postMessage({
            type: "offline-synced",
            temp_id: item.temp_id,
          });
        });
      } catch (err) {
        await OfflineDB.marcarConError(item.temp_id, err.message);
      }
    }
  } catch (err) {
    console.error("[SW] Error sincronizando facturas offline:", err);
  }
}

/* ==========================
   FETCH
========================== */
self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);

  // No cachear PDFs
  if (url.pathname.endsWith(".pdf")) {
    return event.respondWith(
      fetch(event.request).catch(() => caches.match("/offline"))
    );
  }

  // No tocar POSTs (facturas, formularios, etc)
  if (event.request.method !== "GET") {
    return;
  }

  // API & páginas → network first
  if (url.pathname.startsWith("/api")) {
    return; // API no se cachea, ya gestionas offline vía IndexedDB
  }

  // Navegación → network first con fallback
  if (event.request.mode === "navigate") {
    return event.respondWith(networkFirst(event.request));
  }

  // Static → cache first
  return event.respondWith(cacheFirst(event.request));
});

/* ==========================
   STRATEGIES
========================== */
async function cacheFirst(request) {
  const cache = await caches.open(STATIC_CACHE);
  const cached = await cache.match(request);
  if (cached) return cached;

  const response = await fetch(request, { credentials: "include" });
  cache.put(request, response.clone());
  return response;
}

async function networkFirst(request) {
  const cache = await caches.open(DYNAMIC_CACHE);

  try {
    const newRequest = new Request(request, { credentials: "include" });
    const response = await fetch(newRequest);

    // Sesión expirada
    if ([401, 403].includes(response.status)) {
      console.warn("[SW] Sesión expirada → limpiando cache y login");

      await cache.delete("/dashboard");
      await cache.delete("/facturas");

      return fetch("/login", { credentials: "include" });
    }

    // Redirecciones
    if (response.type === "opaqueredirect") {
      return response;
    }

    // Cachear solo HTML válido
    if (
      response.status === 200 &&
      response.headers.get("content-type")?.includes("text/html")
    ) {
      cache.put(request, response.clone());
    }

    return response;
  } catch {
    // OFFLINE
    const cached = await cache.match(request);
    if (cached) return cached;

    return caches.match("/offline");
  }
}
