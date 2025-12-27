from pathlib import Path
from fastapi import HTTPException
import os


def resolver_ruta_pdf_factura(factura, emisor):
    """
    Devuelve:
      base_dir → carpeta donde se guarda
      pdf_path → ruta final del archivo
    Funciona en:
      - Local
      - Render
      - Instalaciones antiguas
    """

    if not factura or not factura.fecha:
        raise HTTPException(400, "Factura sin fecha válida")

    year = factura.fecha.year
    quarter = (factura.fecha.month - 1) // 3 + 1

    # =====================================================
    # 1️⃣ DETERMINAR BASE
    # =====================================================
    # Prioridad real del sistema
    ruta_base = (
        (getattr(emisor, "ruta_pdf", "") or "").strip()
        or (getattr(emisor, "ruta_facturas", "") or "").strip()
    )

    # =========================
    # MODO RENDER / SERVIDOR
    # =========================
    # Si no hay ruta definida → usar /data
    if not ruta_base:
        ruta_base = "/data/facturas"

    base_dir = Path(ruta_base).resolve()

    # =====================================================
    # 2️⃣ ESTRUCTURA: /AÑO/T#
    # =====================================================
    destino = base_dir / str(year) / f"T{quarter}"
    destino.mkdir(parents=True, exist_ok=True)

    # =====================================================
    # 3️⃣ NOMBRE ARCHIVO
    # =====================================================
    numero = str(factura.numero or "SIN_NUMERO").replace("/", "-")
    filename = f"Factura_{numero}.pdf"

    pdf_path = destino / filename

    return destino, pdf_path
