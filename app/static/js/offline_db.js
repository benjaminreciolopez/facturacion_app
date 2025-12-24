// app/static/js/offline_db.js

const OfflineDB = (() => {
  const DB_NAME = "facturacion_offline";
  const DB_VERSION = 3;
  const STORE_FACTURAS = "facturas_borrador";

  function openDB() {
    return new Promise((resolve, reject) => {
      const request = indexedDB.open(DB_NAME, DB_VERSION);

      request.onupgradeneeded = (event) => {
        const db = event.target.result;
        let store;

        if (!db.objectStoreNames.contains(STORE_FACTURAS)) {
          // Primera instalación o BD borrada
          store = db.createObjectStore(STORE_FACTURAS, {
            keyPath: "temp_id",
          });
        } else {
          // Actualización desde v1 o v2
          store = event.target.transaction.objectStore(STORE_FACTURAS);
        }

        // Garantizamos el índice aunque venga de versiones anteriores
        if (!store.indexNames.contains("offline_id")) {
          store.createIndex("offline_id", "temp_id", { unique: true });
        }
      };

      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
  }

  async function saveFacturaBorrador(facturaData) {
    const db = await openDB();

    return new Promise((resolve, reject) => {
      const tx = db.transaction(STORE_FACTURAS, "readwrite");
      const store = tx.objectStore(STORE_FACTURAS);

      const tempId =
        facturaData.temp_id ||
        `offline_${Date.now()}_${Math.random().toString(16).slice(2)}`;

      const record = {
        temp_id: tempId,
        data: facturaData, // aquí metemos TODO lo que luego enviaremos al backend
        created_at: new Date().toISOString(),
        sincronizada: false,
        last_error: null,
      };

      const req = store.put(record);
      req.onsuccess = () => resolve(record);
      req.onerror = () => reject(req.error);
    });
  }

  async function getFacturasPendientes() {
    const db = await openDB();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(STORE_FACTURAS, "readonly");
      const store = tx.objectStore(STORE_FACTURAS);

      const req = store.getAll();

      req.onsuccess = () => {
        const all = req.result || [];
        resolve(all.filter((f) => !f.sincronizada));
      };

      req.onerror = () => reject(req.error);
    });
  }

  async function marcarComoSincronizada(tempId) {
    const db = await openDB();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(STORE_FACTURAS, "readwrite");
      const store = tx.objectStore(STORE_FACTURAS);
      const getReq = store.get(tempId);

      getReq.onsuccess = () => {
        const record = getReq.result;
        if (!record) {
          resolve(false);
          return;
        }
        record.sincronizada = true;
        record.last_error = null;
        const putReq = store.put(record);
        putReq.onsuccess = () => resolve(true);
        putReq.onerror = () => reject(putReq.error);
      };

      getReq.onerror = () => reject(getReq.error);
    });
  }

  async function marcarConError(tempId, errorMsg) {
    const db = await openDB();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(STORE_FACTURAS, "readwrite");
      const store = tx.objectStore(STORE_FACTURAS);
      const getReq = store.get(tempId);

      getReq.onsuccess = () => {
        const record = getReq.result;
        if (!record) {
          resolve(false);
          return;
        }
        record.last_error = errorMsg || "Error desconocido";
        const putReq = store.put(record);
        putReq.onsuccess = () => resolve(true);
        putReq.onerror = () => reject(putReq.error);
      };

      getReq.onerror = () => reject(getReq.error);
    });
  }

  async function getTodas() {
    const db = await openDB();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(STORE_FACTURAS, "readonly");
      const store = tx.objectStore(STORE_FACTURAS);
      const req = store.getAll();

      req.onsuccess = () => resolve(req.result || []);
      req.onerror = () => reject(req.error);
    });
  }

  async function borrar(tempId) {
    const db = await openDB();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(STORE_FACTURAS, "readwrite");
      const store = tx.objectStore(STORE_FACTURAS);
      const req = store.delete(tempId);

      req.onsuccess = () => resolve(true);
      req.onerror = () => reject(req.error);
    });
  }

  return {
    saveFacturaBorrador,
    getFacturasPendientes,
    marcarComoSincronizada,
    marcarConError,
    getTodas,
    borrar,
  };
})();
