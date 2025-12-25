from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlmodel import Session, select

from app.db.session import get_session
from app.core.templates import templates
from app.models.iva import IVA

router = APIRouter(prefix="/configuracion/iva", tags=["IVA"])


# ============================================================
# LISTADO IVA (VISTA)
# ============================================================
@router.get("", response_class=HTMLResponse)
def iva_list_view(
    request: Request,
    session: Session = Depends(get_session),
):
    ivas = session.exec(
        select(IVA)
        .where(IVA.activo == True)
        .order_by(IVA.porcentaje)
    ).all()

    return templates.TemplateResponse(
        "configuracion/iva/list.html",
        {
            "request": request,
            "ivas": ivas,
        },
    )


# ============================================================
# LISTADO IVA (JSON)
# ============================================================
@router.get("/list-json", response_class=JSONResponse)
def iva_list_json(session: Session = Depends(get_session)):
    ivas = session.exec(
        select(IVA)
        .where(IVA.activo == True)
        .order_by(IVA.porcentaje)
    ).all()

    return [
        {
            "id": i.id,
            "porcentaje": i.porcentaje,
            "descripcion": i.descripcion,
        }
        for i in ivas
    ]


# ============================================================
# CREAR IVA
# ============================================================
@router.post("/create")
def iva_create(
    porcentaje: float = Form(...),
    descripcion: str = Form(""),
    session: Session = Depends(get_session),
):
    # Normalizar a 2 decimales para evitar problemas de float
    porcentaje = round(float(porcentaje), 2)

    # Validaciones básicas
    if porcentaje < 0 or porcentaje > 100:
        return RedirectResponse(
            f"/configuracion/iva?error=Porcentaje%20no%20válido",
            status_code=303,
        )

    # Evitar duplicados (sobre el valor redondeado)
    existe = session.exec(
        select(IVA)
        .where(IVA.activo == True)
        .where(IVA.porcentaje == porcentaje)
    ).first()

    if existe:
        return RedirectResponse(
            f"/configuracion/iva?error=Ya%20existe%20un%20IVA%20del%20{porcentaje}%",
            status_code=303,
        )

    iva = IVA(
        porcentaje=porcentaje,
        descripcion=(descripcion or "").strip(),
        activo=True,
    )

    session.add(iva)
    session.commit()

    return RedirectResponse(
        "/configuracion/iva?ok=IVA%20creado%20correctamente",
        status_code=303,
    )


# ============================================================
# DESACTIVAR IVA (SOFT DELETE)
# ============================================================
@router.get("/{iva_id}/delete")
def iva_delete(
    iva_id: int,
    session: Session = Depends(get_session),
):
    iva = session.get(IVA, iva_id)
    if iva:
        iva.activo = False
        session.commit()

    return RedirectResponse(
        "/configuracion/iva",
        status_code=303,
    )
