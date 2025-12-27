# app/routers/debug.py
from fastapi import APIRouter
from pathlib import Path

router = APIRouter(prefix="/debug", tags=["debug"])

@router.get("/uploads")
def listar_uploads():
    base = Path("/data/uploads")
    if not base.exists():
        return {"exists": False, "message": "/data/uploads NO existe"}

    archivos = []
    for p in base.rglob("*"):
        archivos.append(str(p))

    return {
        "exists": True,
        "base": str(base),
        "items": archivos or "VACÍO"
    }
