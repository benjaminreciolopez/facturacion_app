from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import Session
from datetime import date
from pydantic import BaseModel

from app.db.session import get_session
from app.models.factura import Factura
from app.models.linea_factura import LineaFactura
from app.models.empresa import Empresa   # ajusta si tu modelo se llama distinto
from sqlmodel import select
api_router = APIRouter(prefix="/api/offline", tags=["Offline"])


def get_empresa_activa(request: Request, session: Session) -> int:
    """
    Devuelve la empresa activa del usuario.
    Si no hay empresa activa → error.
    """

    empresa_id = request.session.get("empresa_id")

    if not empresa_id:
        raise HTTPException(403, "No hay empresa activa seleccionada")

    empresa = session.get(Empresa, empresa_id)

    if not empresa:
        raise HTTPException(404, "Empresa activa no encontrada")

    return empresa.id


class LineaOffline(BaseModel):
    descripcion: str
    cantidad: float
    precio_unitario: float
    iva: float


class FacturaOfflinePayload(BaseModel):
    cliente_id: int | None = None
    fecha: date | None = None
    lineas: list[LineaOffline]

class FacturaOfflinePayload(BaseModel):
    offline_id: str
    cliente_id: int | None = None
    fecha: date | None = None
    lineas: list[LineaOffline]


@api_router.post("/facturas")
def sync_offline_factura(
    payload: FacturaOfflinePayload,
    request: Request,
    session: Session = Depends(get_session),
):

    if not payload.lineas:
        raise HTTPException(400, "La factura debe tener al menos una línea.")

    empresa_id = get_empresa_activa(request, session)

    # ===============================
    # 1️⃣ Comprobar si ya existe
    # ===============================
    existente = session.exec(
        select(Factura)
        .where(Factura.offline_id == payload.offline_id)
        .where(Factura.empresa_id == empresa_id)
    ).first()

    if existente:
        return {
            "ok": True,
            "id": existente.id,
            "duplicado": True
        }

    # ===============================
    # 2️⃣ Crear factura nueva
    # ===============================
    factura = Factura(
        empresa_id=empresa_id,
        cliente_id=payload.cliente_id,
        fecha=payload.fecha or date.today(),
        estado="BORRADOR",
        offline_id=payload.offline_id,
    )

    session.add(factura)
    session.flush()  # Para tener factura.id

    subtotal = 0
    iva_total = 0

    for l in payload.lineas:
        base = l.cantidad * l.precio_unitario
        cuota = base * (l.iva / 100.0)

        subtotal += base
        iva_total += cuota

        linea = LineaFactura(
            factura_id=factura.id,
            descripcion=l.descripcion,
            cantidad=l.cantidad,
            precio_unitario=l.precio_unitario,
            iva=l.iva,
            total=base + cuota,
        )
        session.add(linea)

    factura.subtotal = subtotal
    factura.iva_total = iva_total
    factura.total = subtotal + iva_total

    session.commit()
    session.refresh(factura)

    return {
        "ok": True,
        "id": factura.id,
        "duplicado": False
    }
