from pathlib import Path
import os
import tempfile


def resolver_ruta_pdf(emisor_ruta: str | None):
    """
    Devuelve una ruta adecuada según entorno:

    LOCAL:
        → Usa carpeta configurada si existe y permite escritura
        → Si no, usa data/pdfs

    RENDER:
        → NUNCA guardamos PDFs de forma persistente
        → Solo /tmp del sistema (temporal real)
    """

    # ============================
    # 1) Si estamos en Render → SOLO TEMP
    # ============================
    if os.getenv("RENDER") or os.getenv("APP_ENV") == "render":
        tmp_dir = Path(tempfile.gettempdir()) / "facturas_tmp"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        return tmp_dir

    # ============================
    # 2) Local – intentar usar carpeta usuario
    # ============================
    if emisor_ruta:
        base = Path(emisor_ruta)
        try:
            base.mkdir(parents=True, exist_ok=True)

            test = base / ".perm_test"
            test.write_text("ok")
            test.unlink()

            return base
        except Exception:
            pass

    # ============================
    # 3) Fallback local seguro
    # ============================
    base = Path("data/pdfs")
    base.mkdir(parents=True, exist_ok=True)
    return base
