from pathlib import Path
import os

def get_pdf_output_dir(config):
    """
    Devuelve una ruta SIEMPRE válida para guardar PDFs.
    Si falla la ruta configurada, usa fallback seguro.
    """

    # 1️⃣ Preferencia: ruta definida en configuración
    if config and config.ruta_facturas_pdf:
        base = Path(config.ruta_facturas_pdf)
    else:
        # 2️⃣ fallback profesional
        base = Path("data/pdfs")

    # 3️⃣ Si estamos en Render usar /tmp obligatoriamente
    if os.getenv("RENDER"):
        base = Path("/tmp/facturas")

    # Crear si no existe
    base.mkdir(parents=True, exist_ok=True)

    # Última comprobación permisos escritura
    test_file = base / ".test"
    try:
        test_file.write_text("ok")
        test_file.unlink()
    except Exception as e:
        # ÚLTIMO fallback seguro
        base = Path("/tmp/facturas")
        base.mkdir(parents=True, exist_ok=True)

    return base
