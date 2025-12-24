let sincronizando = false;

async function sincronizarFacturasPendientes() {
  if (sincronizando) {
    console.log("⏳ Sincronización ya en curso");
    return;
  }

  sincronizando = true;
  console.log("🔄 Buscando facturas offline pendientes…");

  let algunaSincronizada = false;

  try {
    const pendientes = await OfflineDB.getFacturasPendientes();
    if (!pendientes || pendientes.length === 0) {
      console.log("✔ No hay facturas pendientes");
      return;
    }

    for (const f of pendientes) {
      try {
        const res = await fetch("/api/offline/facturas", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            offline_id: f.temp_id,
            ...f.data,
          }),
        });

        const result = await res.json().catch(() => ({}));

        if (!res.ok || !result?.ok) {
          console.warn("❌ Error al sincronizar", result);
          await OfflineDB.marcarConError(
            f.temp_id,
            result?.error || "Error al sincronizar"
          );
          continue;
        }

        console.log("✔ Factura sincronizada", f.temp_id);

        await OfflineDB.marcarComoSincronizada(f.temp_id);
        await OfflineDB.borrar(f.temp_id); // ✅ la quitamos de IndexedDB

        algunaSincronizada = true;

        notificar(
          "Factura sincronizada",
          "Una factura pendiente ha sido guardada correctamente en el servidor."
        );
      } catch (err) {
        console.error("❌ Error conexión servidor", err);
        await OfflineDB.marcarConError(f.temp_id, err.message);
      }
    }
  } finally {
    sincronizando = false;

    if (!algunaSincronizada) return;

    const path = window.location.pathname;

    // ✅ Si estamos en listado normal -> recargar
    if (path === "/facturas" || path === "/facturas/") {
      location.reload();
      return;
    }

    // ✅ Si estamos en la página offline -> limpiar y mandar al listado
    if (path.startsWith("/facturas/offline")) {
      window.location.href = "/facturas";
      return;
    }

    // 🔹 En cualquier otra página no molestamos
  }
}

let syncTimer = null;

window.addEventListener("online", () => {
  console.log("🌍 Conexión restaurada");

  clearTimeout(syncTimer);
  syncTimer = setTimeout(() => {
    notificar(
      "Conexión restaurada",
      "Se iniciará la sincronización automática."
    );
    sincronizarFacturasPendientes();
  }, 800);
});

window.addEventListener("offline", () => {
  console.log("📴 Sin conexión");
  notificar("Modo offline activo", "Las facturas se guardarán como borrador.");
});

// ======================
// Notificador universal
// ======================
function notificar(titulo, mensaje) {
  try {
    // Prefer Notification API si está permitido
    if ("Notification" in window) {
      if (Notification.permission === "granted") {
        new Notification(titulo, { body: mensaje });
        return;
      } else if (Notification.permission !== "denied") {
        Notification.requestPermission().then((perm) => {
          if (perm === "granted") {
            new Notification(titulo, { body: mensaje });
          }
        });
        return;
      }
    }
  } catch {}

  // Fallback visible
  alert(`${titulo}\n\n${mensaje}`);
}
