from fastapi import APIRouter, Request, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse
from pathlib import Path
import os
import shutil
from app.core.templates import templates
import mimetypes

router = APIRouter(prefix="/storage", tags=["Storage"])

BASE_PATH = Path("/data").resolve()


def require_admin(request: Request):
    user = request.session.get("user")
    if not user or user.get("rol") != "admin":
        raise HTTPException(403, "Acceso restringido a administradores")


def safe_path(rel_path: str) -> Path:
    """
    Seguridad: evita ../ traversal y garantiza que siempre esté en /data
    """
    if ".." in rel_path:
        raise HTTPException(400, "Ruta no válida")

    final = (BASE_PATH / rel_path).resolve()

    if not str(final).startswith(str(BASE_PATH)):
        raise HTTPException(400, "Ruta fuera de almacenamiento permitido")

    return final

@router.get("")
def storage_index(request: Request):
    require_admin(request)

    items = []

    if not BASE_PATH.exists():
        return {"ok": True, "items": []}

    for p in BASE_PATH.rglob("*"):
        rel = p.relative_to(BASE_PATH)

        items.append({
            "nombre": p.name,
            "ruta": str(rel),
            "tipo": "dir" if p.is_dir() else "file",
            "tamano": p.stat().st_size if p.is_file() else None
        })

    return {"ok": True, "items": items}


@router.delete("")
def storage_delete(request: Request, path: str):
    require_admin(request)
    final = safe_path(path)

    if not final.exists():
        raise HTTPException(404, "No existe")

    if final.is_dir():
        shutil.rmtree(final)
    else:
        final.unlink()

    return {"ok": True}


@router.get("/ui", response_class=HTMLResponse)
def storage_explorer(
    request: Request,
    path: str = Query("/data"),
):
    base = "/data"

    # Seguridad: impedir salir de /data
    path = os.path.normpath(path)
    if not path.startswith(base):
        path = base

    if not os.path.exists(path):
        raise HTTPException(404, "Ruta no encontrada")

    elementos = []

    for nombre in os.listdir(path):
        ruta = os.path.join(path, nombre)
        es_dir = os.path.isdir(ruta)

        elementos.append({
            "nombre": nombre,
            "ruta": ruta.replace("\\", "/"),
            "tipo": "Carpeta" if es_dir else "Archivo",
            "tamano": None if es_dir else os.path.getsize(ruta),
            "es_dir": es_dir,
        })

    # Breadcrumb
    partes = path.split("/")
    breadcrumb = []
    acumulado = ""

    for p in partes:
        if not p:
            continue
        acumulado += "/" + p
        breadcrumb.append({
            "nombre": p,
            "ruta": acumulado
        })

    return templates.TemplateResponse(
        "storage/list.html",
        {
            "request": request,
            "path": path,
            "elementos": elementos,
            "breadcrumb": breadcrumb
        }
    )



@router.get("/storage/view")
def storage_view(path: str = Query(...)):
    real_path = Path(path).resolve()

    # Seguridad → no permitir salir de /data
    if BASE_PATH not in real_path.parents and real_path != BASE_PATH:
        raise HTTPException(403, "Acceso no permitido")

    if not real_path.exists():
        raise HTTPException(404, "Archivo no encontrado")

    if real_path.is_dir():
        raise HTTPException(400, "No se puede previsualizar una carpeta")

    # Detectar MIME
    mime, _ = mimetypes.guess_type(real_path.name)
    if not mime:
        mime = "application/octet-stream"

    return FileResponse(
        real_path,
        media_type=mime,
        filename=real_path.name,            # nombre correcto
        headers={
            "Content-Disposition": f'inline; filename="{real_path.name}"'
        }
    )
@router.get("/storage/download")
def storage_download(path: str = Query(...)):
    real_path = Path(path).resolve()

    # Seguridad → evitar salir de /data
    if BASE_PATH not in real_path.parents and real_path != BASE_PATH:
        raise HTTPException(403, "Acceso no permitido")

    if not real_path.exists():
        raise HTTPException(404, "Archivo no encontrado")

    if real_path.is_dir():
        raise HTTPException(400, "No se puede descargar una carpeta")

    return FileResponse(
        real_path,
        media_type="application/octet-stream",
        filename=real_path.name,                       # nombre correcto
        headers={
            "Content-Disposition": f'attachment; filename="{real_path.name}"'
        },
    )