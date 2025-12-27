from pathlib import Path
import os


def resolver_ruta_pdf(emisor_ruta: str | None):
    """
    Devuelve SIEMPRE una ruta válida de escritura.
    Prioridades:
    1) Ruta definida por el usuario (si existe y tiene permisos)
    2) /tmp/facturas (Render / Linux seguro)
    3) data/pdfs (local seguro proyecto)
    """

    posibles = []

    # Ruta configurada por el usuario
    if emisor_ruta:
        posibles.append(Path(emisor_ruta))

    # Render u otros servicios → /tmp obligatorio
    if os.getenv("RENDER"):
        posibles.append(Path("/tmp/facturas"))

    # fallback local seguro
    posibles.append(Path("data/pdfs"))

    for base in posibles:
        try:
            base.mkdir(parents=True, exist_ok=True)

            test = base / ".perm_test"
            test.write_text("ok")
            test.unlink()

            return base
        except Exception:
            continue

    # Si TODO falla (casi imposible), última red
    base = Path("/tmp/facturas_final")
    base.mkdir(parents=True, exist_ok=True)
    return base
