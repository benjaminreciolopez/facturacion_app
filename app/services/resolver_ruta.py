from pathlib import Path
from fastapi import HTTPException
import os


def resolver_ruta_pdf_factura(factura, emisor):
    """
    Devuelve:
      base_dir → carpeta donde se guarda
      pdf_path → ruta final del archivo

    Reglas:
      ✔ Siempre guarda en /data cuando está en servidor
      ✔ Usa solo nombre lógico (ruta_facturas)
      ✔ Compatible con instalaciones antiguas (ruta_pdf local)
    """

    if not factura or not factura.fecha:
        raise HTTPException(400, "Factura sin fecha válida")

    year = factura.fecha.year
    quarter = (factura.fecha.month - 1) // 3 + 1

    # =====================================================
    # 1️⃣ NUEVO SISTEMA → NOMBRE LÓGICO
    # =====================================================
    nombre_carpeta = (getattr(emisor, "ruta_facturas", "") or "").strip()

    if nombre_carpeta:
        # Seguridad: limpiar posibles rutas absolutas antiguas
        nombre_carpeta = nombre_carpeta.replace("\\", "/")
        nombre_carpeta = nombre_carpeta.split("/")[-1]   # solo nombre puro

        base_root = Path("/data") / nombre_carpeta

    else:
        # =====================================================
        # 2️⃣ COMPATIBILIDAD SISTEMAS ANTIGUOS
        # Solo válido en local. En Render ignoramos rutas del host.
        # =====================================================
        legacy = (getattr(emisor, "ruta_pdf", "") or "").strip()

        if legacy and not os.getenv("RENDER"):
            base_root = Path(legacy)
        else:
            base_root = Path("/data/facturas")

    # =====================================================
    # 3️⃣ ESTRUCTURA /AÑO/T#
    # =====================================================
    destino = base_root / str(year) / f"T{quarter}"
    destino.mkdir(parents=True, exist_ok=True)

    # =====================================================
    # 4️⃣ NOMBRE ARCHIVO
    # =====================================================
    numero = str(factura.numero or "SIN_NUMERO").replace("/", "-")
    filename = f"Factura_{numero}.pdf"

    pdf_path = destino / filename

    return destino, pdf_path
