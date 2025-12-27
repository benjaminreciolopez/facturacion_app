from pathlib import Path
from fastapi import HTTPException

def resolver_ruta_pdf_factura(factura, emisor):
    year = factura.fecha.year
    quarter = (factura.fecha.month - 1) // 3 + 1

    carpeta = (emisor.carpeta_pdf_nombre or "").strip()
    if not carpeta:
        raise HTTPException(400, "No hay carpeta PDF configurada")

    base_dir = Path("/data") / carpeta / str(year) / f"T{quarter}"
    base_dir.mkdir(parents=True, exist_ok=True)

    filename = f"Factura_{factura.numero}.pdf"
    return base_dir, base_dir / filename
