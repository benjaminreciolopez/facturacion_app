from fastapi import APIRouter, Request, Depends, Query
from fastapi.responses import HTMLResponse
from sqlmodel import Session, select
from datetime import date
from app.db.session import get_session
from app.core.templates import templates
from app.models.auditoria import Auditoria

router = APIRouter(prefix="/auditoria", tags=["Auditoría"])


@router.get("", response_class=HTMLResponse)
def auditoria_list(
    request: Request,
    entidad: str | None = Query(None),
    entidad_id: int | None = Query(None),   # ⬅️ NUEVO
    accion: str | None = Query(None),
    resultado: str | None = Query(None),
    fecha_desde: date | None = Query(None),
    fecha_hasta: date | None = Query(None),
    session: Session = Depends(get_session),
):
    query = select(Auditoria)

    if entidad:
        query = query.where(Auditoria.entidad == entidad)

    if entidad_id:
        query = query.where(Auditoria.entidad_id == entidad_id)

    if accion:
        query = query.where(Auditoria.accion == accion)

    if resultado:
        query = query.where(Auditoria.resultado == resultado)

    if fecha_desde:
        query = query.where(Auditoria.created_at >= fecha_desde)

    if fecha_hasta:
        query = query.where(Auditoria.created_at <= fecha_hasta)

    eventos = session.exec(
        query.order_by(Auditoria.created_at.desc())
    ).all()


    return templates.TemplateResponse(
        "auditoria/list.html",
        {
            "request": request,
            "eventos": eventos,
            "filtros": {
                "entidad": entidad,
                "entidad_id": entidad_id,
                "accion": accion,
                "resultado": resultado,
                "fecha_desde": fecha_desde,
                "fecha_hasta": fecha_hasta,
            },
        },
    )
