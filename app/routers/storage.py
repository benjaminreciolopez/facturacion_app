from fastapi import APIRouter, Request, HTTPException, Query, Body
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from pathlib import Path
import os
import shutil
from app.core.templates import templates
import mimetypes
from datetime import datetime

router = APIRouter(prefix="/storage", tags=["Storage"])

BASE_PATH = Path("/data").resolve()

DISK_TOTAL_BYTES = 1024 * 1024 * 1024  # 1 GB

TRASH_DIR = BASE_PATH / ".trash"
TRASH_DIR.mkdir(parents=True, exist_ok=True)

SYSTEM_NAMES = {".trash"}  # iremos añadiendo más nombres de carpetas del sistema

PROTECTED_ROOTS = {
    ".trash",          # papelera
    "facturas_pdf",    # donde guardes PDFs
    "certificados",    # certificados
}

def get_storage_usage() -> dict:
    used = 0
    if BASE_PATH.exists():
        for p in BASE_PATH.rglob("*"):
            if p.is_file():
                try:
                    used += p.stat().st_size
                except OSError:
                    continue

    used = min(used, DISK_TOTAL_BYTES)
    free = max(DISK_TOTAL_BYTES - used, 0)
    percent = round(used / DISK_TOTAL_BYTES * 100, 2)

    return {
        "total": DISK_TOTAL_BYTES,
        "used": used,
        "free": free,
        "percent": percent,
    }


def require_admin(request: Request):
    user = request.session.get("user")
    if not user or user.get("rol") != "admin":
        raise HTTPException(403, "Acceso restringido a administradores")


def safe_path(rel_path: str) -> Path:
    rel_path = rel_path.strip("/")

    if rel_path.startswith("data/"):
        rel_path = rel_path.replace("data/", "", 1)

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

    # No borrar raíces críticas directamente
    rel = final.relative_to(BASE_PATH)

    # No permitir borrar las carpetas raíz protegidas
    if len(rel.parts) == 1 and rel.parts[0] in PROTECTED_ROOTS:
        raise HTTPException(403, "Carpeta raíz del sistema protegida")

    move_to_trash(final)

    return {"ok": True, "moved_to_trash": str(rel)}


DANGEROUS_EXT = {".exe", ".sh", ".bat", ".ps1", ".cmd", ".bd"}

@router.get("/view")
def storage_view(path: str = Query(...)):
    real_path = safe_path(path)

    if not real_path.exists():
        raise HTTPException(404, "Archivo no encontrado")

    if real_path.is_dir():
        raise HTTPException(400, "No se puede previsualizar una carpeta")

    if real_path.suffix.lower() in DANGEROUS_EXT:
        raise HTTPException(400, "Tipo de archivo no permitido para vista previa")

    mime, _ = mimetypes.guess_type(real_path.name)
    if not mime:
        mime = "application/octet-stream"

    return FileResponse(
        real_path,
        media_type=mime,
        filename=real_path.name,
        headers={"Content-Disposition": f'inline; filename="{real_path.name}"'}
    )

@router.get("/download")
def storage_download(path: str = Query(...)):
    real_path = safe_path(path)

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

@router.get("/trash/ui", response_class=HTMLResponse)
def storage_trash_ui(request: Request):
    require_admin(request)

    path = str(TRASH_DIR)

    if not TRASH_DIR.exists():
        elementos = []
    else:
        elementos = []
        for p in TRASH_DIR.rglob("*"):
            rel = p.relative_to(TRASH_DIR)
            elementos.append({
                "nombre": p.name,
                "ruta": str(rel),
                "tipo": "Carpeta" if p.is_dir() else "Archivo",
                "tamano": None if p.is_dir() else p.stat().st_size,
                "es_dir": p.is_dir(),
            })

    breadcrumb = [
        {"nombre": "Almacenamiento", "ruta": "/storage/ui"},
        {"nombre": "Papelera", "ruta": "/storage/trash/ui"}
    ]

    usage = get_storage_usage()

    return templates.TemplateResponse(
        "storage/list.html",
        {
            "request": request,
            "path": "/data/.trash",
            "elementos": elementos,
            "breadcrumb": breadcrumb,
            "show_hidden": True,
            "trash_view": True,
            "usage": usage,
        }
    )

def move_to_trash(path: Path) -> Path:
    """
    Mueve un archivo/carpeta a .trash manteniendo la estructura relativa.
    Devuelve la ruta de destino.
    """
    rel = path.relative_to(BASE_PATH)
    destino = TRASH_DIR / rel
    destino.parent.mkdir(parents=True, exist_ok=True)

    shutil.move(str(path), str(destino))
    return destino



@router.get("/trash")
def storage_trash(request: Request):
    require_admin(request)

    items = []
    if TRASH_DIR.exists():
        for p in TRASH_DIR.rglob("*"):
            rel = p.relative_to(TRASH_DIR)
            items.append({
                "nombre": p.name,
                "ruta": str(rel),
                "tipo": "dir" if p.is_dir() else "file",
                "tamano": p.stat().st_size if p.is_file() else None
            })
    return {"ok": True, "items": items}


@router.post("/trash/restore")
def storage_trash_restore(request: Request, path: str = Query(...)):
    require_admin(request)

    src = (TRASH_DIR / path).resolve()
    if TRASH_DIR not in src.parents and src != TRASH_DIR:
        raise HTTPException(400, "Ruta inválida en papelera")

    if not src.exists():
        raise HTTPException(404, "No existe en papelera")

    dest = BASE_PATH / path
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dest))

    return {"ok": True, "restored": path}

@router.post("/trash/batch-restore")
def storage_trash_batch_restore(request: Request, payload: dict = Body(...)):
    require_admin(request)

    paths = payload.get("paths") or []
    if not isinstance(paths, list) or not paths:
        raise HTTPException(400, "Debe indicar al menos una ruta")

    restored = []

    for rel in paths:
        src = (TRASH_DIR / rel).resolve()

        if TRASH_DIR not in src.parents and src != TRASH_DIR:
            continue
        if not src.exists():
            continue

        dest = BASE_PATH / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dest))
        restored.append(rel)

    return {"ok": True, "restored": restored}

@router.post("/batch/delete")
def storage_batch_delete(request: Request, payload: dict = Body(...)):
    require_admin(request)

    paths = payload.get("paths") or []
    if not isinstance(paths, list) or not paths:
        raise HTTPException(400, "Debe indicar al menos una ruta")

    moved = []

    for raw in paths:
        final = safe_path(raw)

        if not final.exists():
            continue

        rel = final.relative_to(BASE_PATH)

        # Proteger raíces críticas
        if rel.parts and rel.parts[0] in PROTECTED_ROOTS and rel == Path(rel.parts[0]):
            continue

        move_to_trash(final)
        moved.append(str(rel))

    return {"ok": True, "moved": moved}

@router.post("/trash/batch-delete")
def storage_trash_batch_delete(request: Request, payload: dict = Body(...)):
    require_admin(request)

    paths = payload.get("paths") or []
    if not isinstance(paths, list) or not paths:
        raise HTTPException(400, "Debe indicar al menos una ruta")

    deleted = 0

    for rel in paths:
        target = (TRASH_DIR / rel).resolve()

        if TRASH_DIR not in target.parents and target != TRASH_DIR:
            continue
        if not target.exists():
            continue

        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink()

        deleted += 1

    return {"ok": True, "deleted": deleted}

@router.delete("/trash/empty")
def storage_trash_empty(request: Request):
    require_admin(request)

    if not TRASH_DIR.exists():
        return {"ok": True, "deleted": 0}

    count = 0
    for p in TRASH_DIR.rglob("*"):
        if p.is_file():
            p.unlink()
            count += 1
    # opcional: limpiar carpetas vacías
    for p in sorted(TRASH_DIR.rglob("*"), reverse=True):
        if p.is_dir():
            try:
                p.rmdir()
            except OSError:
                pass

    return {"ok": True, "deleted": count}

@router.get("/ui", response_class=HTMLResponse)
def storage_explorer(
    request: Request,
    path: str = Query("/data"),
    show_hidden: bool = Query(False),
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

        # Ocultar elementos del sistema/ocultos
        if not show_hidden:
            if nombre.startswith(".") or nombre in SYSTEM_NAMES:
                continue

        elementos.append({
            "nombre": nombre,
            "ruta": ruta.replace("\\", "/"),
            "tipo": "Carpeta" if es_dir else "Archivo",
            "tamano": None if es_dir else os.path.getsize(ruta),
            "es_dir": es_dir,
        })

    # Breadcrumb igual que antes...
    partes = path.split("/")
    breadcrumb = []
    acumulado = ""
    for p in partes:
        if not p:
            continue
        acumulado += "/" + p
        breadcrumb.append({"nombre": p, "ruta": acumulado})

    usage = get_storage_usage()

    return templates.TemplateResponse(
        "storage/list.html",
        {
            "request": request,
            "path": path,
            "elementos": elementos,
            "breadcrumb": breadcrumb,
            "show_hidden": show_hidden,
            "usage": usage,
        }
    )

import zipfile
from io import BytesIO

FACTURAS_DIR = BASE_PATH / "facturas_pdf"

@router.get("/zip/facturas")
def storage_zip_facturas(
    request: Request,
    year: int = Query(..., ge=2000, le=2100),
):
    require_admin(request)

    year_dir = FACTURAS_DIR / str(year)
    if not year_dir.exists():
        raise HTTPException(404, "No hay PDFs para ese año")

    mem_file = BytesIO()
    with zipfile.ZipFile(mem_file, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for p in year_dir.rglob("*.pdf"):
            arcname = p.relative_to(FACTURAS_DIR)
            zf.write(p, arcname=str(arcname))

    mem_file.seek(0)
    filename = f"facturas_{year}.zip"

    return StreamingResponse(
        mem_file,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        },
    )

@router.post("/batch/zip")
def storage_batch_zip(request: Request, payload: dict = Body(...)):
    require_admin(request)

    paths = payload.get("paths") or []
    if not isinstance(paths, list) or not paths:
        raise HTTPException(400, "Debe indicar al menos una ruta")

    mem_file = BytesIO()

    with zipfile.ZipFile(mem_file, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for raw in paths:
            base = safe_path(raw)

            if not base.exists():
                continue

            if base.is_dir():
                for p in base.rglob("*"):
                    if p.is_file():
                        arcname = p.relative_to(BASE_PATH)
                        zf.write(p, arcname=str(arcname))
            else:
                arcname = base.relative_to(BASE_PATH)
                zf.write(base, arcname=str(arcname))

    mem_file.seek(0)
    filename = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"

    return StreamingResponse(
        mem_file,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        },
    )
